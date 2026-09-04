"""
gitlab_int/review_agent.py
A DEDICATED code-review agent — separate from the GitLab chat agent.

It does one thing: take a diff (a merge request, a single commit vs its parent,
or an arbitrary commit range) and return a structured verdict:

    {
      "rating":        "good" | "need_to_check" | "bad",
      "risk_factor":   "low" | "medium" | "high",
      "risk_score":    0-100,
      "summary":       "...",
      "findings":      [ {severity, title, detail, file} ],
      "good_points":   [ "...", ... ],
      "recommendation":"approve" | "request_changes" | "reject"
    }

It compares the previous code to the proposed code and judges correctness,
security, error handling, edge cases, performance, and test coverage.

One deterministic Bedrock call (temperature 0) — NOT an Observe→Think→Act loop.
The shared LLM singleton (agent.llm.get_llm) is reused; no new client.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent.llm import get_llm
from gitlab_int.gitlab_client import clip_text
from gitlab_int.mr_tools import gitlab_mr_changes, gitlab_mr_get
from gitlab_int.project_tools import gitlab_commit_diff, gitlab_compare

logger = logging.getLogger(__name__)

_RATINGS = {"good", "need_to_check", "bad"}
_RISKS = {"low", "medium", "high"}
_RECS = {"approve", "request_changes", "reject"}

REVIEW_SYSTEM = """You are a meticulous senior software engineer performing a \
pre-merge code review. You are given the PREVIOUS code and the PROPOSED change \
(a unified diff). Judge whether the proposed change is safe to merge.

Assess, in order of importance:
1. Correctness — logic errors, wrong conditions, off-by-one, broken control flow,
   regressions vs the previous code.
2. Security — injection, auth/authorization gaps, secrets in code, unsafe
   deserialization, SSRF, path traversal.
3. Error handling & edge cases — nulls, empty inputs, network/IO failure,
   concurrency, unbounded loops.
4. Performance — N+1 queries, needless O(n^2), large allocations, blocking calls.
5. Tests & observability — is the change covered? are logs/metrics adequate?
6. Maintainability — naming, dead code, duplication, unclear intent.

Return your verdict as a SINGLE JSON object and NOTHING else, with EXACTLY these keys:
{
  "rating": "good" | "need_to_check" | "bad",
  "risk_factor": "low" | "medium" | "high",
  "risk_score": <integer 0-100, higher = riskier>,
  "summary": "<2-4 sentence overall assessment>",
  "findings": [
    {"severity": "high"|"medium"|"low", "title": "<short>", "detail": "<what & why & fix>", "file": "<path or ''>"}
  ],
  "good_points": ["<positive observation>", ...],
  "recommendation": "approve" | "request_changes" | "reject"
}

Rules:
- "good"          → no blocking issues; minor nits at most.
- "need_to_check" → plausibly fine but has ambiguity, missing tests, or medium risks a human must verify.
- "bad"           → at least one high-severity correctness/security problem, or many medium ones.
- If the diff is empty or unreadable, return rating "need_to_check", risk_factor "medium",
  and say so in the summary.
- Be concrete: name files, functions, and line intent. No generic advice.
"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _coerce_verdict(raw_text: str) -> dict:
    """Parse the LLM output into a normalized verdict dict (never raises)."""
    obj: dict[str, Any] = {}
    m = _JSON_RE.search(raw_text or "")
    if m:
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            obj = {}

    rating = str(obj.get("rating", "")).strip().lower().replace(" ", "_").replace("-", "_")
    if rating in {"needs_check", "check", "review", "caution", "warning"}:
        rating = "need_to_check"
    if rating not in _RATINGS:
        rating = "need_to_check"

    risk = str(obj.get("risk_factor", "")).strip().lower()
    if risk not in _RISKS:
        risk = {"good": "low", "bad": "high"}.get(rating, "medium")

    try:
        score = int(round(float(obj.get("risk_score"))))
    except (TypeError, ValueError):
        score = {"low": 20, "medium": 55, "high": 85}[risk]
    score = max(0, min(100, score))

    rec = str(obj.get("recommendation", "")).strip().lower().replace(" ", "_")
    if rec not in _RECS:
        rec = {"good": "approve", "need_to_check": "request_changes", "bad": "reject"}[rating]

    findings = []
    for f in obj.get("findings", []) or []:
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity", "medium")).strip().lower()
        if sev not in {"high", "medium", "low"}:
            sev = "medium"
        findings.append(
            {
                "severity": sev,
                "title": str(f.get("title", "")).strip() or "(untitled finding)",
                "detail": str(f.get("detail", "")).strip(),
                "file": str(f.get("file", "")).strip(),
            }
        )
    findings.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])

    good_points = [str(x).strip() for x in (obj.get("good_points") or []) if str(x).strip()]

    summary = str(obj.get("summary", "")).strip()
    if not summary:
        summary = (
            raw_text.strip()[:600]
            if raw_text and not m
            else "The reviewer did not return a usable summary."
        )

    return {
        "rating": rating,
        "risk_factor": risk,
        "risk_score": score,
        "summary": summary,
        "findings": findings,
        "good_points": good_points,
        "recommendation": rec,
        "parsed_ok": bool(m and obj),
    }


def _run_review(meta: dict, diff_text: str) -> dict:
    """Build the prompt, call Bedrock once, return a normalized verdict + meta."""
    diff_text = clip_text(diff_text or "")
    header_lines = [f"{k}: {v}" for k, v in meta.items() if v not in (None, "", [])]
    prompt = (
        "## Change under review\n"
        + "\n".join(header_lines)
        + "\n\n## Unified diff (previous code → proposed code)\n"
        + "```diff\n"
        + (diff_text or "(empty diff)")
        + "\n```\n\n"
        "Return ONLY the JSON verdict object described in the system prompt."
    )
    try:
        raw = get_llm().chat(
            messages=[{"role": "user", "content": prompt}],
            system=REVIEW_SYSTEM,
            max_tokens=2200,
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Review LLM call failed")
        return {
            "error": True,
            "message": f"Review model call failed: {exc}",
            "rating": "need_to_check",
            "risk_factor": "medium",
            "risk_score": 50,
            "summary": "The review could not be completed because the model call failed.",
            "findings": [],
            "good_points": [],
            "recommendation": "request_changes",
            **meta,
        }

    verdict = _coerce_verdict(raw)
    verdict.update(meta)
    return verdict


# ---------------------------------------------------------------------------
# Public entry points (also registered as agent tools)
# ---------------------------------------------------------------------------


def gitlab_review_merge_request(project_id: str, mr_iid: int) -> dict:
    """
    TOOL: gitlab_review_merge_request
    AI code review of a merge request: pulls the full MR diff (previous vs
    proposed) and returns a structured verdict with a risk factor and a
    good / need_to_check / bad rating.
    """
    changes = gitlab_mr_changes(project_id=project_id, mr_iid=mr_iid)
    try:
        mr = gitlab_mr_get(project_id=project_id, mr_iid=mr_iid)
    except Exception:  # noqa: BLE001
        mr = {}
    meta = {
        "kind": "merge_request",
        "project": changes.get("project"),
        "mr_iid": mr_iid,
        "title": changes.get("title"),
        "description": clip_text(changes.get("description") or "", 1500),
        "author": changes.get("author"),
        "source_branch": changes.get("source_branch"),
        "target_branch": changes.get("target_branch"),
        "base_sha": changes.get("base_sha"),
        "head_sha": changes.get("head_sha"),
        "files_changed": changes.get("file_count"),
        "merge_status": mr.get("detailed_merge_status") or mr.get("merge_status"),
        "has_conflicts": mr.get("has_conflicts"),
        "web_url": mr.get("web_url"),
    }
    return _run_review(meta, changes.get("text", ""))


def gitlab_review_commit(project_id: str, sha: str) -> dict:
    """
    TOOL: gitlab_review_commit
    AI code review of a single commit — compares it against its parent
    ("previous commit → current commit") and returns a structured verdict.
    """
    diff = gitlab_commit_diff(project_id=project_id, sha=sha)
    parents = diff.get("parent_ids") or []
    meta = {
        "kind": "commit",
        "project": diff.get("project"),
        "sha": sha,
        "parent_sha": parents[0] if parents else "(root commit)",
        "files_changed": diff.get("file_count"),
    }
    return _run_review(meta, diff.get("text", ""))


def gitlab_review_commit_range(project_id: str, from_sha: str, to_sha: str) -> dict:
    """
    TOOL: gitlab_review_commit_range
    AI code review of everything between two refs (from_sha = last known-good,
    to_sha = new head). Returns a structured verdict.
    """
    cmp = gitlab_compare(project_id=project_id, from_sha=from_sha, to_sha=to_sha)
    meta = {
        "kind": "commit_range",
        "project": cmp.get("project"),
        "from": from_sha,
        "to": to_sha,
        "commits": cmp.get("commit_count"),
        "files_changed": cmp.get("file_count"),
    }
    return _run_review(meta, cmp.get("text", ""))
