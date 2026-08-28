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

from bitbucket.bitbucket_http import _fmt_pr, _get, _post, _put, _workspace
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


# ---------------------------------------------------------------------------
# bitbucket_* tools (exact names requested by the agent spec)
# ---------------------------------------------------------------------------


def _src_and_dest(
    source_branch: str = "",
    destination_branch: str = "",
) -> tuple[dict, dict]:
    """Build Bitbucket source/destination branch objects for PR creation."""
    source: dict[str, Any] = {"branch": {"name": source_branch or "main"}}
    dest: dict[str, Any] = {"branch": {"name": destination_branch or "main"}}
    return source, dest


def bitbucket_pr_create(
    repo_slug: str,
    title: str,
    source_branch: str = "",
    destination_branch: str = "",
    description: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pr_create
    Create a pull request. Scope: write:pullrequest:bitbucket, read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug          : str – destination repository slug
    title              : str – PR title
    source_branch      : str – source branch (defaults to repo default branch)
    destination_branch : str – destination branch (defaults to repo default branch)
    description        : str – optional PR description
    workspace          : str

    Returns
    -------
    dict with the created PR id, title and links (or error JSON).
    """
    ws = workspace or _workspace()
    source, dest = _src_and_dest(
        source_branch=source_branch,
        destination_branch=destination_branch,
    )
    payload: dict[str, Any] = {
        "title": title,
        "source": source,
        "destination": dest,
    }
    if description:
        payload["description"] = description
    data = _post(f"/repositories/{ws}/{repo_slug}/pullrequests", payload)
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "workspace": ws,
        "repo": repo_slug,
        "link": ((data.get("links") or {}).get("html") or {}).get("href"),
    }


def bitbucket_pr_list(
    repo_slug: str,
    state: str = "OPEN",
    workspace: str = "",
    pagelen: int = 50,
) -> dict:
    """
    TOOL: bitbucket_pr_list
    List pull requests for a repository. Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug : str
    state     : str – OPEN | MERGED | DECLINED | SUPERSEDED (default OPEN)
    workspace : str
    pagelen   : int – page size (Bitbucket caps at 50 for PRs)

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../pullrequests).
    """
    ws = workspace or _workspace()
    return _get(
        f"/repositories/{ws}/{repo_slug}/pullrequests",
        {"state": state, "pagelen": pagelen},
    )


def bitbucket_pr_get(repo_slug: str, pr_id: int | None = None, workspace: str = "") -> dict:
    """
    TOOL: bitbucket_pr_get
    Get details for a single pull request. Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug : str
    pr_id     : int
    workspace : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../pullrequests/{pr_id}).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}")


def bitbucket_pr_diff(repo_slug: str, pr_id: int | None = None, workspace: str = "") -> dict:
    """
    TOOL: bitbucket_pr_diff
    Get the diff of a pull request. Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug : str
    pr_id     : int
    workspace : str

    Returns
    -------
    Raw diff content from the Bitbucket API.
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/diff")


def bitbucket_pr_merge(
    repo_slug: str,
    pr_id: int | None = None,
    merge_strategy: str = "merge_commit",
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: bitbucket_pr_merge
    Merge (fulfill) a pull request. HUMAN-GATED — requires confirmed=True.
    Scope: write:pullrequest:bitbucket.
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "bitbucket_pr_merge",
            "summary": f"Merge pull request #{pr_id} in {ws}/{repo_slug}",
            "reason": "Merging a PR is a destructive action — pass confirmed=True to execute.",
        }
    data = _post(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/merge",
        {"merge_strategy": merge_strategy},
    )
    return {
        "action": "bitbucket_pr_merge",
        "merged": True,
        "pr_id": pr_id,
        "repo": f"{ws}/{repo_slug}",
        "state": data.get("state"),
    }


def bitbucket_pr_approve(
    repo_slug: str,
    pr_id: int | None = None,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: bitbucket_pr_approve
    Approve a pull request. HUMAN-GATED — requires confirmed=True.
    Scope: write:pullrequest:bitbucket.
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "bitbucket_pr_approve",
            "summary": f"Approve pull request #{pr_id} in {ws}/{repo_slug}",
            "reason": "Approving a PR is a review action — pass confirmed=True to execute.",
        }
    _post(f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/approve")
    return {"action": "bitbucket_pr_approve", "pr_id": pr_id, "repo": f"{ws}/{repo_slug}"}


def bitbucket_pr_decline(
    repo_slug: str,
    pr_id: int | None = None,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: bitbucket_pr_decline
    Decline a pull request. HUMAN-GATED — requires confirmed=True.
    Scope: write:pullrequest:bitbucket.
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "bitbucket_pr_decline",
            "summary": f"Decline pull request #{pr_id} in {ws}/{repo_slug}",
            "reason": "Declining a PR is a review action — pass confirmed=True to execute.",
        }
    _post(f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/decline")
    return {
        "action": "bitbucket_pr_decline",
        "declined": True,
        "pr_id": pr_id,
        "repo": f"{ws}/{repo_slug}",
    }


def bitbucket_pr_comment_list(
    repo_slug: str, pr_id: int | None = None, workspace: str = ""
) -> dict:
    """
    TOOL: bitbucket_pr_comment_list
    List comments on a pull request. Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug : str
    pr_id     : int
    workspace : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../comments).
    """
    ws = workspace or _workspace()
    return _get(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/comments", {"pagelen": 100}
    )


def bitbucket_pr_comment_add(
    repo_slug: str,
    pr_id: int | None = None,
    content: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pr_comment_add
    Add a comment to a pull request. Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug : str
    pr_id     : int
    content   : str – comment text
    workspace : str

    Returns
    -------
    dict with the created comment id and content.
    """
    ws = workspace or _workspace()
    data = _post(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/comments",
        {"content": {"raw": content}},
    )
    return {
        "id": data.get("id"),
        "content": (data.get("content") or {}).get("raw"),
        "created_on": data.get("created_on"),
    }


def bitbucket_pr_comment_update(
    repo_slug: str,
    pr_id: int | None = None,
    comment_id: int | None = None,
    content: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pr_comment_update
    Update an existing PR comment (only comments owned by the caller).
    Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug  : str
    pr_id      : int
    comment_id : int
    content    : str – updated comment text
    workspace  : str

    Returns
    -------
    dict with the updated comment id and content.
    """
    ws = workspace or _workspace()
    data = _put(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/comments/{comment_id}",
        {"content": {"raw": content}},
    )
    return {"id": data.get("id"), "content": (data.get("content") or {}).get("raw")}


def bitbucket_pr_task_list(
    repo_slug: str, pr_id: int | None = None, workspace: str = ""
) -> dict:
    """
    TOOL: bitbucket_pr_task_list
    List tasks on a pull request. Scope: read:pullrequest:bitbucket.

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../tasks).
    """
    ws = workspace or _workspace()
    return _get(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/tasks", {"pagelen": 100}
    )


def bitbucket_pr_task_create(
    repo_slug: str,
    pr_id: int | None = None,
    content: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pr_task_create
    Create a task on a pull request. Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug : str
    pr_id     : int
    content   : str – task text
    workspace : str

    Returns
    -------
    dict with the created task id, content and state.
    """
    ws = workspace or _workspace()
    data = _post(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/tasks",
        {"content": {"raw": content}},
    )
    return {
        "id": data.get("id"),
        "content": (data.get("content") or {}).get("raw"),
        "state": data.get("state"),
    }


def bitbucket_pr_task_update(
    repo_slug: str,
    pr_id: int | None = None,
    task_id: int | None = None,
    content: str = "",
    state: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pr_task_update
    Update a PR task (change its text and/or resolve state). Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    repo_slug : str
    pr_id     : int
    task_id   : int
    content   : str – updated task text (optional)
    state     : str – RESOLVED | UNRESOLVED (optional)
    workspace : str

    Returns
    -------
    dict with the updated task id, content and state.
    """
    ws = workspace or _workspace()
    payload: dict[str, Any] = {}
    if content:
        payload["content"] = {"raw": content}
    if state:
        payload["state"] = state
    data = _put(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/tasks/{task_id}", payload
    )
    return {
        "id": data.get("id"),
        "content": (data.get("content") or {}).get("raw"),
        "state": data.get("state"),
    }


def bitbucket_user_pull_requests(
    selected_user: str,
    workspace: str = "",
    state: str = "OPEN",
) -> dict:
    """
    TOOL: bitbucket_user_pull_requests
    Get pull requests authored by a user across the workspace.
    Scope: read:pullrequest:bitbucket.

    Parameters
    ----------
    selected_user : str – username or user UUID of the author
    workspace     : str
    state         : str – OPEN | MERGED | DECLINED | SUPERSEDED (default OPEN)

    Returns
    -------
    Raw parsed JSON from the Bitbucket API
    (GET /workspaces/{workspace}/pullrequests/{selected_user}).
    """
    ws = workspace or _workspace()
    from bitbucket.workspace_tools import _normalize_uuid

    return _get(f"/workspaces/{ws}/pullrequests/{_normalize_uuid(selected_user)}", {"state": state, "pagelen": 50})
