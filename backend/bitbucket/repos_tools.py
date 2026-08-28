"""
bitbucket/repos_tools.py
Repository tools — clone-friendly CRUD, enumeration, source-content writes,
raw-file reads, permissions and commit history.

Every function returns plain JSON-serialisable dicts/lists so results drop
straight into the LLM context. Destructive/irreversible actions (delete_repo)
are HUMAN-GATED and require an explicit `confirmed: True` flag.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from bitbucket.bitbucket_http import (
    _del,
    _fmt_commit,
    _fmt_repo,
    _get,
    _post,
    _post_form,
    _put,
    _workspace,
)

logger = logging.getLogger(__name__)


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


def list_repos(workspace: str = "") -> list[dict]:
    """
    TOOL: list_repos
    List ALL repositories in a Bitbucket workspace.

    Parameters
    ----------
    workspace : str
    """
    ws = workspace or _workspace()
    data = _get(f"/repositories/{ws}", {"pagelen": 100})
    return [_fmt_repo(r) for r in data.get("values", [])]


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
    from config.settings import BITBUCKET_AUTH, BITBUCKET_BASE_URL

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
