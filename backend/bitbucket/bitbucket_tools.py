"""
bitbucket/bitbucket_tools.py
Bitbucket tools — a completely separate tool layer from ClickUp.

Each function is a callable the Bitbucket agent can dispatch. Functions return
plain JSON-serialisable dicts/lists (never raw HTTP responses) so results can be
dropped straight into the LLM context, exactly like the ClickUp tool layer.

Authentication
--------------
Bitbucket requires HTTP Basic Auth using the `email:api_token` credential pair
(settings.BITBUCKET_AUTH). All calls go to https://api.bitbucket.org/2.0/.

Human-gated actions
-------------------
Destructive / irreversible tools (approve, decline, merge, delete_repo) require
an explicit `confirmed: True` flag before they execute. Without it they return a
`needs_confirmation` payload describing exactly what would happen.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import BITBUCKET_AUTH, BITBUCKET_BASE_URL, BITBUCKET_HEADERS, BITBUCKET_WORKSPACE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared HTTP helper
# ---------------------------------------------------------------------------


def _request(
    method: str,
    endpoint: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> Any:
    url = f"{BITBUCKET_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.request(
        method,
        url,
        auth=BITBUCKET_AUTH,
        headers=BITBUCKET_HEADERS,
        params=params or {},
        json=json_body,
        timeout=30,
    )
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


def _get(endpoint: str, params: dict | None = None) -> Any:
    return _request("GET", endpoint, params=params)


def _post(endpoint: str, payload: dict | None = None, params: dict | None = None) -> Any:
    return _request("POST", endpoint, json_body=payload, params=params)


def _put(endpoint: str, payload: dict | None = None) -> Any:
    return _request("PUT", endpoint, json_body=payload)


def _post_form(endpoint: str, data: dict) -> Any:
    """POST with form-encoded data (used by the source-content write API)."""
    url = f"{BITBUCKET_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.post(
        url,
        auth=BITBUCKET_AUTH,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


def _del(endpoint: str) -> Any:
    return _request("DELETE", endpoint)


def _workspace() -> str:
    """Return the configured default workspace (may be empty)."""
    return BITBUCKET_WORKSPACE


# ---------------------------------------------------------------------------
# Normalisers
# ---------------------------------------------------------------------------


def _fmt_repo(r: dict) -> dict:
    return {
        "name": r.get("name"),
        "full_name": r.get("full_name"),
        "uuid": r.get("uuid"),
        "slug": r.get("slug"),
        "language": r.get("language"),
        "is_private": r.get("is_private"),
        "description": r.get("description"),
        "created_on": r.get("created_on"),
        "updated_on": r.get("updated_on"),
        "mainbranch": (r.get("mainbranch") or {}).get("name"),
        "links": {
            "html": ((r.get("links") or {}).get("html") or {}).get("href"),
        },
    }


def _fmt_commit(c: dict) -> dict:
    author = c.get("author") or {}
    user = author.get("user") or {}
    return {
        "hash": c.get("hash"),
        "message": (c.get("message") or "").strip(),
        "author": user.get("display_name") or author.get("raw") or c.get("author") or "unknown",
        "email": (user.get("email") or author.get("email") or ""),
        "date": c.get("date"),
    }


def _fmt_pr(pr: dict) -> dict:
    source = (pr.get("source") or {}) | {}
    destination = (pr.get("destination") or {}) | {}
    return {
        "id": pr.get("id"),
        "title": pr.get("title"),
        "description": pr.get("description"),
        "state": pr.get("state"),
        "created_on": pr.get("created_on"),
        "updated_on": pr.get("updated_on"),
        "author": ((pr.get("author") or {}).get("display_name") or ""),
        "source_branch": (source.get("branch") or {}).get("name"),
        "destination_branch": (destination.get("branch") or {}).get("name"),
        "links": {
            "html": ((pr.get("links") or {}).get("html") or {}).get("href"),
        },
    }


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


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


def create_repo(
    repo_name: str,
    workspace: str = "",
    is_private: bool = True,
    description: str = "",
    language: str = "",
) -> dict:
    """
    TOOL: create_repo
    Create a new repository in the workspace.

    Parameters
    ----------
    repo_name   : str – repository name/slug
    workspace   : str
    is_private  : bool
    description : str
    language    : str
    """
    payload: dict[str, Any] = {"is_private": is_private}
    if description:
        payload["description"] = description
    if language:
        payload["language"] = language
    data = _post(f"/repositories/{workspace or _workspace()}/{repo_name}", payload)
    return _fmt_repo(data)


def delete_repo(
    repo_slug: str,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: delete_repo
    Delete a repository. HUMAN-GATED — requires confirmed=True.
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "delete_repo",
            "summary": f"Permanently delete repository {ws}/{repo_slug}",
            "reason": "Deleting a repository is irreversible — pass confirmed=True to execute.",
        }
    _del(f"/repositories/{ws}/{repo_slug}")
    return {"deleted": True, "repo": f"{ws}/{repo_slug}"}


def create_branch(
    repo_slug: str,
    branch_name: str,
    from_commit: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: create_branch
    Create a branch from a given commit SHA (or the default branch if omitted).

    Parameters
    ----------
    repo_slug   : str
    branch_name : str – new branch name
    from_commit : str – source commit SHA
    workspace   : str
    """
    payload: dict[str, Any] = {"name": branch_name}
    if from_commit:
        payload["target"] = {"hash": from_commit}
    data = _post(f"/repositories/{workspace or _workspace()}/{repo_slug}/refs/branches", payload)
    return {
        "name": data.get("name"),
        "target": (data.get("target") or {}).get("hash"),
        "repo": f"{workspace or _workspace()}/{repo_slug}",
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


def set_branch_permission(
    repo_slug: str,
    branch_pattern: str,
    kind: str,
    value: str,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: set_branch_permission
    Set branch restrictions/permissions for a repository.

    Parameters
    ----------
    repo_slug       : str
    branch_pattern  : str – e.g. "main", "release/*"
    kind            : str – push | delete | require_tasks_to_be_completed | require_passing_builds_to_merge etc.
    value           : str – the restriction value / flat string
    workspace       : str
    confirmed       : bool
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "set_branch_permission",
            "summary": f"Set branch restriction '{kind}' on '{branch_pattern}' in {ws}/{repo_slug}",
            "reason": "Changing branch permissions affects the whole team — pass confirmed=True to execute.",
        }
    # Bitbucket branch restrictions API (v2.0)
    payload: dict[str, Any] = {
        "kind": kind,
        "pattern": branch_pattern,
    }
    if value:
        payload["value"] = value
    data = _post(f"/repositories/{ws}/{repo_slug}/branch-restrictions", payload)
    return {
        "action": "set_branch_permission",
        "restriction_id": data.get("id"),
        "kind": data.get("kind"),
        "pattern": data.get("pattern"),
        "branching_model": None,
    }


def invite_collaborator(
    repo_slug: str,
    email_or_uuid: str,
    role: str = "write",
    workspace: str = "",
) -> dict:
    """
    TOOL: invite_collaborator
    Grant a user access to a repository with a specified role.

    Parameters
    ----------
    repo_slug      : str
    email_or_uuid  : str – user email or UUID
    role           : str – read | write | admin
    workspace      : str
    """
    payload: dict[str, Any] = {
        "permission": role,
    }
    try:
        data = _put(
            f"/repositories/{workspace or _workspace()}/{repo_slug}/permissions-config/users/{email_or_uuid}",
            payload,
        )
    except requests.HTTPError:
        # Fallback: create a membership directly if the config endpoint is not available
        data = _post(
            f"/repositories/{workspace or _workspace()}/{repo_slug}/permissions-config/users",
            {"user": {"email": email_or_uuid}, "permission": role},
        )
    return {
        "action": "invite_collaborator",
        "user": email_or_uuid,
        "role": role,
        "repo": f"{workspace or _workspace()}/{repo_slug}",
        "data": data,
    }


def get_repository_permissions(
    repo_slug: str,
    user_email_or_uuid: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: get_repository_permissions
    Get permissions for a specific user on a repository (or the full user list).

    Parameters
    ----------
    repo_slug          : str
    user_email_or_uuid : str – optional filter for a single user
    workspace          : str
    """
    ws = workspace or _workspace()
    if user_email_or_uuid:
        try:
            data = _get(
                f"/repositories/{ws}/{repo_slug}/permissions-config/users/{user_email_or_uuid}"
            )
            return {
                "user": user_email_or_uuid,
                "permission": data.get("permission"),
                "role": data.get("role"),
            }
        except requests.HTTPError:
            return {"error": f"No user permission record found for {user_email_or_uuid}"}
    data = _get(f"/repositories/{ws}/{repo_slug}/permissions-config/users")
    return {
        "repo": f"{ws}/{repo_slug}",
        "users": [
            {
                "user": ((u.get("user") or {}).get("display_name") or ""),
                "email": ((u.get("user") or {}).get("email") or ""),
                "uuid": ((u.get("user") or {}).get("uuid") or ""),
                "permission": u.get("permission"),
                "type": u.get("type"),
            }
            for u in data.get("values", [])
        ],
    }


def push_to_repo(
    repo_slug: str,
    file_path: str,
    content: str,
    message: str,
    branch: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: push_to_repo
    Push changes to a repository via the Bitbucket source-content API
    (creates or updates a file on a branch).

    Parameters
    ----------
    repo_slug : str
    file_path : str – path in the repo, e.g. "docs/api.md"
    content   : str – new file content
    message   : str – commit message
    branch    : str – target branch (defaults to repo main branch)
    workspace : str
    """
    ws = workspace or _workspace()
    if not branch:
        repo = _get(f"/repositories/{ws}/{repo_slug}")
        branch = (repo.get("mainbranch") or {}).get("name") or "main"
    data = _post_form(
        f"/repositories/{ws}/{repo_slug}/src",
        {
            "message": message,
            "branch": branch,
            file_path: content,
        },
    )
    return {
        "action": "push_to_repo",
        "repo": f"{ws}/{repo_slug}",
        "file": file_path,
        "branch": branch,
        "commit_hash": data.get("hash"),
    }


def pull_repo_info(repo_slug: str, workspace: str = "") -> dict:
    """
    TOOL: pull_repo_info
    Pull / read repository metadata and the top-level file listing (src).

    Parameters
    ----------
    repo_slug : str
    workspace : str
    """
    ws = workspace or _workspace()
    repo = _get(f"/repositories/{ws}/{repo_slug}")
    try:
        src = _get(f"/repositories/{ws}/{repo_slug}/src")
        files = [
            {
                "path": p.get("path"),
                "type": p.get("type"),
                "commit": ((p.get("commit") or {}).get("hash")),
            }
            for p in src.get("values", [])
        ]
    except requests.HTTPError:
        files = []
    return {
        "repo": _fmt_repo(repo),
        "files": files,
    }


def get_latest_commits(repo_slug: str = "", workspace: str = "", limit: int = 10) -> list[dict]:
    """
    TOOL: get_latest_commits
    Fetch the latest commits for a repository (who, when, message). If no repo
    is given, surfaces the latest commits across all repositories in the
    workspace.

    Parameters
    ----------
    repo_slug : str – optional single repository
    workspace : str
    limit     : int – number of commits to return (default 10)
    """
    ws = workspace or _workspace()
    if repo_slug:
        repos = [repo_slug]
    else:
        repos = [r["slug"] for r in list_repos(ws)]
    commits: list[dict] = []
    for slug in repos:
        try:
            data = _get(
                f"/repositories/{ws}/{slug}/commits",
                {"pagelen": max(1, min(limit, 100))},
            )
        except requests.HTTPError as exc:
            logger.warning("Could not fetch commits for %s/%s: %s", ws, slug, exc)
            continue
        for c in data.get("values", []):
            f = _fmt_commit(c)
            f["repo"] = f"{ws}/{slug}"
            commits.append(f)
        if len(commits) >= limit:
            break
    return commits[:limit]


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
            data = _get(
                f"/repositories/{ws}/{slug}/pullrequests",
                {"state": "OPEN", "pagelen": 100},
            )
        except requests.HTTPError as exc:
            logger.warning("Could not fetch PRs for %s/%s: %s", ws, slug, exc)
            continue
        for pr in data.get("values", []):
            f = _fmt_pr(pr)
            f["repo"] = f"{ws}/{slug}"
            pending.append(f)
    return pending


def get_raw_file(
    repo_slug: str,
    path: str,
    revision: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: get_raw_file
    Access a raw file (the download / raw-file section permission). Reads the
    unrendered content of a file at a given path in the repo at a revision
    (defaults to the repository's main branch / HEAD).

    Parameters
    ----------
    repo_slug : str
    path      : str – file path in the repo, e.g. "README.md" or "src/main.py"
    revision  : str – branch name or commit SHA; empty = default branch
    workspace : str
    """
    ws = workspace or _workspace()
    revision = revision or "HEAD"
    url = f"/repositories/{ws}/{repo_slug}/src/{revision}/{path.lstrip('/')}"
    resp = requests.get(
        f"{BITBUCKET_BASE_URL}/{url}",
        auth=BITBUCKET_AUTH,
        headers={"Accept": "text/plain"},
        timeout=30,
    )
    resp.raise_for_status()
    return {
        "action": "get_raw_file",
        "repo": f"{ws}/{repo_slug}",
        "path": path,
        "revision": revision,
        "content": resp.text,
    }


def list_webhooks(repo_slug: str, workspace: str = "") -> list[dict]:
    """
    TOOL: list_webhooks
    List all webhooks configured on a repository.

    Parameters
    ----------
    repo_slug : str
    workspace : str
    """
    data = _get(f"/repositories/{workspace or _workspace()}/{repo_slug}/hooks")
    return [
        {
            "uuid": h.get("uuid"),
            "url": h.get("url"),
            "description": h.get("description"),
            "active": h.get("active"),
            "events": h.get("events", []),
        }
        for h in data.get("values", [])
    ]


def add_webhook(
    repo_slug: str,
    url: str,
    events: list[str] | None = None,
    description: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: add_webhook
    Add a webhook to a repository for the given event types.

    Parameters
    ----------
    repo_slug    : str
    url          : str – callback URL for the webhook
    events       : list[str] – e.g. ["repo:push", "pullrequest:created"]
    description  : str
    workspace    : str
    """
    payload: dict[str, Any] = {"url": url, "events": events or ["repo:push"]}
    if description:
        payload["description"] = description
    data = _post(
        f"/repositories/{workspace or _workspace()}/{repo_slug}/hooks",
        payload,
    )
    return {
        "action": "add_webhook",
        "uuid": data.get("uuid"),
        "url": data.get("url"),
        "events": data.get("events", []),
        "active": data.get("active"),
    }


def remove_webhook(
    repo_slug: str,
    hook_uuid: str,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: remove_webhook
    Delete a webhook from a repository. HUMAN-GATED — requires confirmed=True.

    Parameters
    ----------
    repo_slug   : str
    hook_uuid   : str – the webhook UUID (from list_webhooks)
    workspace   : str
    confirmed   : bool
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "remove_webhook",
            "summary": f"Remove webhook {hook_uuid} from {ws}/{repo_slug}",
            "reason": "Removing a webhook stops events from being delivered — pass confirmed=True to execute.",
        }
    _del(f"/repositories/{ws}/{repo_slug}/hooks/{hook_uuid}")
    return {
        "action": "remove_webhook",
        "deleted": True,
        "hook_uuid": hook_uuid,
        "repo": f"{ws}/{repo_slug}",
    }


def get_application_properties(
    repo_slug: str,
    app_key: str,
    name: str,
    scope: str = "repository",
    pr_id: str = "",
    commit: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: get_application_properties
    Read an application property for a commit / repository / pull request.

    Parameters
    ----------
    repo_slug : str
    app_key   : str – the application / add-on key
    name      : str – property name
    scope     : str – repository | pull_request | commit
    pr_id     : str – required when scope=pull_request
    commit    : str – required when scope=commit
    workspace : str
    """
    ws = workspace or _workspace()
    path = _property_path(ws, repo_slug, scope, pr_id, commit, name)
    data = _get(path)
    return {
        "action": "get_application_properties",
        "scope": scope,
        "app_key": app_key,
        "name": name,
        "value": data,
    }


def update_application_properties(
    repo_slug: str,
    app_key: str,
    name: str,
    value: Any,
    scope: str = "repository",
    pr_id: str = "",
    commit: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: update_application_properties
    Update (PUT) an application property for a commit / repository / PR.

    Parameters
    ----------
    repo_slug : str
    app_key   : str
    name      : str
    value     : any – the JSON value to store
    scope     : str – repository | pull_request | commit
    pr_id     : str
    commit    : str
    workspace : str
    """
    ws = workspace or _workspace()
    path = _property_path(ws, repo_slug, scope, pr_id, commit, name)
    data = _put(path, {"value": value})
    return {
        "action": "update_application_properties",
        "scope": scope,
        "name": name,
        "updated": True,
        "data": data,
    }


def delete_application_properties(
    repo_slug: str,
    app_key: str,
    name: str,
    scope: str = "repository",
    pr_id: str = "",
    commit: str = "",
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: delete_application_properties
    Delete an application property for a commit / repository / PR.
    HUMAN-GATED — requires confirmed=True.

    Parameters
    ----------
    repo_slug : str
    app_key   : str
    name      : str
    scope     : str – repository | pull_request | commit
    pr_id     : str
    commit    : str
    workspace : str
    confirmed : bool
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "delete_application_properties",
            "summary": f"Delete application property '{name}' ({app_key}) on {scope} in {ws}/{repo_slug}",
            "reason": "Deleting a property is irreversible — pass confirmed=True to execute.",
        }
    path = _property_path(ws, repo_slug, scope, pr_id, commit, name)
    _del(path)
    return {
        "action": "delete_application_properties",
        "deleted": True,
        "scope": scope,
        "name": name,
    }


def _property_path(
    ws: str, repo_slug: str, scope: str, pr_id: str, commit: str, name: str
) -> str:
    """Build the Bitbucket application-properties endpoint path for a scope."""
    base = f"/repositories/{ws}/{repo_slug}"
    if scope == "pull_request":
        return f"{base}/pullrequests/{pr_id}/properties/{name}/"
    if scope == "commit":
        return f"{base}/commit/{commit}/properties/{name}/"
    return f"{base}/properties/{name}/"


def list_repos(workspace: str = "") -> list[dict]:
    """Utility used internally to enumerate repositories in a workspace."""
    ws = workspace or _workspace()
    data = _get(f"/repositories/{ws}", {"pagelen": 100})
    return [_fmt_repo(r) for r in data.get("values", [])]


# ---------------------------------------------------------------------------
# Registry — mirrors the ClickUp tools/__init__.py pattern
# ---------------------------------------------------------------------------


def _bt(name, fn, description, params=None):
    return {"name": name, "fn": fn, "description": description, "params": params or []}


BITBUCKET_TOOL_REGISTRY: list[dict] = [
    _bt("get_pr_diff", get_pr_diff,
        "Fetch the diff of a pull request for a given repo and PR ID.",
        [{"name": "workspace", "type": "str", "required": False},
         {"name": "repo_slug", "type": "str", "required": True},
         {"name": "pr_id", "type": "int", "required": True}]),
    _bt("post_pr_comment", post_pr_comment,
        "Post a review comment on a pull request.",
        [{"name": "workspace", "type": "str", "required": False},
         {"name": "repo_slug", "type": "str", "required": True},
         {"name": "pr_id", "type": "int", "required": True},
         {"name": "content", "type": "str", "required": True}]),
    _bt("approve_pr", approve_pr,
        "Approve a pull request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "workspace", "type": "str", "required": False},
         {"name": "repo_slug", "type": "str", "required": True},
         {"name": "pr_id", "type": "int", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("decline_pr", decline_pr,
        "Decline a pull request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "workspace", "type": "str", "required": False},
         {"name": "repo_slug", "type": "str", "required": True},
         {"name": "pr_id", "type": "int", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("create_repo", create_repo,
        "Create a new repository in the workspace.",
        [{"name": "repo_name", "type": "str", "required": True},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "is_private", "type": "bool", "required": False, "default": True},
         {"name": "description", "type": "str", "required": False},
         {"name": "language", "type": "str", "required": False}]),
    _bt("delete_repo", delete_repo,
        "Delete a repository. HUMAN-GATED — requires confirmed=True.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("create_branch", create_branch,
        "Create a branch from a given commit SHA.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "branch_name", "type": "str", "required": True},
         {"name": "from_commit", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("merge_pr", merge_pr,
        "Merge / fulfill a pull request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "workspace", "type": "str", "required": False},
         {"name": "repo_slug", "type": "str", "required": True},
         {"name": "pr_id", "type": "int", "required": True},
         {"name": "merge_strategy", "type": "str", "required": False, "default": "merge_commit"},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("set_branch_permission", set_branch_permission,
        "Set branch restrictions / permissions on a repository. HUMAN-GATED.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "branch_pattern", "type": "str", "required": True},
         {"name": "kind", "type": "str", "required": True},
         {"name": "value", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("invite_collaborator", invite_collaborator,
        "Invite a user to a repository with a specified role.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "email_or_uuid", "type": "str", "required": True},
         {"name": "role", "type": "str", "required": False, "default": "write"},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("get_repository_permissions", get_repository_permissions,
        "Get permissions for a specific user (or all users) on a repository.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "user_email_or_uuid", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("push_to_repo", push_to_repo,
        "Push changes to a repository via the source-content API (update/create a file).",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "file_path", "type": "str", "required": True},
         {"name": "content", "type": "str", "required": True},
         {"name": "message", "type": "str", "required": True},
         {"name": "branch", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("pull_repo_info", pull_repo_info,
        "Pull / read repository metadata and file listing.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("get_latest_commits", get_latest_commits,
        "Fetch the latest 10 commits for a repo (who, when, message).",
        [{"name": "repo_slug", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "limit", "type": "int", "required": False, "default": 10}]),
    _bt("get_pending_prs", get_pending_prs,
        "Fetch all open pull requests waiting for review (repo, author, title).",
        [{"name": "repo_slug", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("get_raw_file", get_raw_file,
        "Access a raw file (the raw-file / download section permission). Read unrendered file content at a path.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "path", "type": "str", "required": True},
         {"name": "revision", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("list_webhooks", list_webhooks,
        "List all webhooks configured on a repository.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("add_webhook", add_webhook,
        "Add a webhook to a repository for the given event types.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "url", "type": "str", "required": True},
         {"name": "events", "type": "list[str]", "required": False},
         {"name": "description", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("remove_webhook", remove_webhook,
        "Delete a webhook from a repository. HUMAN-GATED — requires confirmed=True.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "hook_uuid", "type": "str", "required": True},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("get_application_properties", get_application_properties,
        "Read an application property for a commit / repository / pull request.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "app_key", "type": "str", "required": True},
         {"name": "name", "type": "str", "required": True},
         {"name": "scope", "type": "str", "required": False, "default": "repository"},
         {"name": "pr_id", "type": "str", "required": False},
         {"name": "commit", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("update_application_properties", update_application_properties,
        "Update (PUT) an application property for a commit / repository / PR.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "app_key", "type": "str", "required": True},
         {"name": "name", "type": "str", "required": True},
         {"name": "value", "type": "any", "required": True},
         {"name": "scope", "type": "str", "required": False, "default": "repository"},
         {"name": "pr_id", "type": "str", "required": False},
         {"name": "commit", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("delete_application_properties", delete_application_properties,
        "Delete an application property for a commit / repository / PR. HUMAN-GATED — requires confirmed=True.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "app_key", "type": "str", "required": True},
         {"name": "name", "type": "str", "required": True},
         {"name": "scope", "type": "str", "required": False, "default": "repository"},
         {"name": "pr_id", "type": "str", "required": False},
         {"name": "commit", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
]

# Lookup by name
BITBUCKET_TOOL_MAP: dict[str, dict] = {t["name"]: t for t in BITBUCKET_TOOL_REGISTRY}
