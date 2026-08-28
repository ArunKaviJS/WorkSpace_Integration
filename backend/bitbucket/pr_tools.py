"""
bitbucket/pr_tools.py
Pull-request tools — diffs, review comments, and reviewer actions
(approve / decline / merge) plus pending-PR discovery.

Reviewer actions (approve, decline, merge) are HUMAN-GATED and require an
explicit `confirmed: True` flag before they run, so the agent can never act
on a PR without the user's confirmation.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from bitbucket.bitbucket_http import _fmt_pr, _get, _post, _workspace
from bitbucket.repos_tools import list_repos

logger = logging.getLogger(__name__)


def get_pr_diff(workspace: str = "", repo_slug: str = "", pr_id: int | None = None) -> dict:
    """
    TOOL: get_pr_diff
    Fetch the diff of a pull request for a given repository and PR ID.

    Parameters
    ----------
    workspace : str – Bitbucket workspace (defaults to BITBUCKET_WORKSPACE)
    repo_slug : str – repository slug/name
    pr_id     : int – pull request ID
    """
    data = _get(f"/repositories/{workspace or _workspace()}/{repo_slug}/pullrequests/{pr_id}/diff")
    return data


def post_pr_comment(
    workspace: str = "",
    repo_slug: str = "",
    pr_id: int | None = None,
    content: str = "",
) -> dict:
    """
    TOOL: post_pr_comment
    Post a review comment on a pull request.

    Parameters
    ----------
    workspace : str
    repo_slug : str
    pr_id     : int
    content   : str – comment text
    """
    data = _post(
        f"/repositories/{workspace or _workspace()}/{repo_slug}/pullrequests/{pr_id}/comments",
        {"content": {"raw": content}},
    )
    return {
        "id": data.get("id"),
        "content": (data.get("content") or {}).get("raw"),
        "created_on": data.get("created_on"),
    }


def approve_pr(
    workspace: str = "",
    repo_slug: str = "",
    pr_id: int | None = None,
    confirmed: bool = False,
) -> dict:
    """
    TOOL: approve_pr
    Approve a pull request. HUMAN-GATED — requires confirmed=True.
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "approve_pr",
            "summary": f"Approve pull request #{pr_id} in {ws}/{repo_slug}",
            "reason": "Approving a PR is a review action — pass confirmed=True to execute.",
        }
    data = _post(f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/approve")
    return {
        "action": "approve_pr",
        "approved": True,
        "pr_id": pr_id,
        "repo": f"{ws}/{repo_slug}",
        "data": _fmt_pr(data.get("pullrequest", data)),
    }


def decline_pr(
    workspace: str = "",
    repo_slug: str = "",
    pr_id: int | None = None,
    confirmed: bool = False,
) -> dict:
    """
    TOOL: decline_pr
    Decline a pull request. HUMAN-GATED — requires confirmed=True.
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "decline_pr",
            "summary": f"Decline pull request #{pr_id} in {ws}/{repo_slug}",
            "reason": "Declining a PR is a review action — pass confirmed=True to execute.",
        }
    data = _post(f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/decline")
    return {
        "action": "decline_pr",
        "declined": True,
        "pr_id": pr_id,
        "repo": f"{ws}/{repo_slug}",
        "data": _fmt_pr(data),
    }


def merge_pr(
    workspace: str = "",
    repo_slug: str = "",
    pr_id: int | None = None,
    merge_strategy: str = "merge_commit",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: merge_pr
    Merge (fulfill) a pull request. HUMAN-GATED — requires confirmed=True.

    Parameters
    ----------
    workspace      : str
    repo_slug      : str
    pr_id          : int
    merge_strategy : str – merge_commit | squash | fast_forward
    confirmed      : bool
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "merge_pr",
            "summary": f"Merge pull request #{pr_id} in {ws}/{repo_slug} ({merge_strategy})",
            "reason": "Merging a PR is a destructive action — pass confirmed=True to execute.",
        }
    data = _post(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/merge",
        {"merge_strategy": merge_strategy},
    )
    return {
        "action": "merge_pr",
        "merged": True,
        "pr_id": pr_id,
        "repo": f"{ws}/{repo_slug}",
        "state": data.get("state"),
        "data": _fmt_pr(data),
    }


def get_pending_prs(repo_slug: str = "", workspace: str = "") -> list[dict]:
    """
    TOOL: get_pending_prs
    Fetch all open pull requests waiting for review (repo, author, title). If
    no repo is given, scans all repositories in the workspace.

    Parameters
    ----------
    repo_slug : str – optional single repository
    workspace : str
    """
    ws = workspace or _workspace()
    if repo_slug:
        repos = [repo_slug]
    else:
        repos = [r["slug"] for r in list_repos(ws)]
    pending: list[dict] = []
    for slug in repos:
        try:
            # NOTE: Bitbucket caps /pullrequests pagelen at 50 (BCLOUD-13229);
            # 100 triggers a 400 "Invalid pagelen" error.
            data = _get(
                f"/repositories/{ws}/{slug}/pullrequests",
                {"state": "OPEN", "pagelen": 50},
            )
        except requests.HTTPError as exc:
            logger.warning("Could not fetch PRs for %s/%s: %s", ws, slug, exc)
            continue
        for pr in data.get("values", []):
            f = _fmt_pr(pr)
            f["repo"] = f"{ws}/{slug}"
            pending.append(f)
    return pending
