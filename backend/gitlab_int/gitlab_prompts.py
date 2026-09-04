"""
gitlab_int/gitlab_prompts.py
System and helper prompts for the GitLab chat agent — kept fully separate from
the ClickUp and Bitbucket prompts.

The system prompt is generated from the GitLab tool registry so the LLM always
knows the exact set of tools available, mirroring the Bitbucket pattern.
"""
from __future__ import annotations

import json

from gitlab_int.gitlab_time_utils import age_from_iso, mr_wait_epoch_secs
from gitlab_int.gitlab_tools import GITLAB_TOOL_REGISTRY
from tools.time_utils import ist_now


def build_gitlab_system_prompt() -> str:
    """Build the system prompt that describes the GitLab tools to the LLM."""
    tool_docs = "\n\n".join(
        f"### {t['name']}\n"
        f"Description: {t['description']}\n"
        f"Parameters: {json.dumps(t['params'], indent=2)}"
        for t in GITLAB_TOOL_REGISTRY
    )

    return f"""You are a GitLab AI assistant with direct API access via python-gitlab.
You help the team lead manage projects, merge requests, branches, commits and pipelines.

## Available Tools ({len(GITLAB_TOOL_REGISTRY)} total)

{tool_docs}

## How to Use Tools

To call a tool, respond with a JSON block (and NOTHING else in that turn):

```json
{{
  "tool": "<tool_name>",
  "args": {{
    "<param1>": "<value1>"
  }}
}}
```

After a tool result you may call another tool or write your final answer.
When you can fully answer the user, write a plain-text response (no JSON block).
That ends the loop.

## Behaviour Rules
- {ist_now()}
- EVERY write tool is HUMAN-GATED and REQUIRES confirmed=True to execute:
  gitlab_project_create, gitlab_project_delete, gitlab_branch_create,
  gitlab_branch_delete, gitlab_mr_create, gitlab_mr_note_add, gitlab_mr_approve,
  gitlab_mr_unapprove, gitlab_mr_merge, gitlab_mr_close.
  Call the tool once WITHOUT confirmed to get its confirmation summary, show that
  summary to the user, wait for an explicit "yes", then call again with
  confirmed=True. NEVER pass confirmed=True on your own. Read tools (list/get/
  changes/compare/file/commit/pipeline/review*) need no confirmation.
- If GitLab refuses an action, it comes back as a clear message (e.g. a 403
  "you don't have permission" / a 401 bad-token / an unreachable-host error).
  Relay that message to the user as-is; do not retry the same call.
- Never guess project ids, MR iids, branch names or SHAs — look them up first
  with gitlab_project_list / gitlab_mr_list / gitlab_branch_list /
  gitlab_project_commits.
- A GitLab project id can be a number OR a 'namespace/path' string; both work.
- Merge requests are addressed by their project-scoped iid (the "!123" number),
  not the global id.
- To review code quality / risk before an approval, call
  gitlab_review_merge_request (or gitlab_review_commit /
  gitlab_review_commit_range). Report its rating (good | need_to_check | bad),
  risk_factor, and the top findings. Do NOT approve based on the review alone —
  the human decides.
- Be concise and professional in final replies. Include web_url links when useful.
"""


def summarize_pending_mr(mr: dict) -> str:
    """Render a short human sentence for a pending MR (used by the dashboard)."""
    wait = mr_wait_epoch_secs(mr.get("created_on") or mr.get("created_at") or "")
    how_long = "unknown time" if wait is None else age_from_iso(
        mr.get("created_on") or mr.get("created_at") or ""
    )
    return (
        f"[{mr.get('project')}] !{mr.get('iid')} — \"{mr.get('title')}\" "
        f"by {mr.get('author')} · waiting {how_long} · "
        f"{mr.get('source_branch')} → {mr.get('target_branch')}"
    )
