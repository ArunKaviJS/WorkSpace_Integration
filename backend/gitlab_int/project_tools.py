"""
gitlab_int/project_tools.py
Project / repository tools — enumerate projects, read commits, files and diffs,
and compare arbitrary refs.

Every function returns plain JSON-serialisable dicts/lists so results drop
straight into the LLM context. Read-only — nothing here mutates a project.
"""
from __future__ import annotations

import logging
from typing import Any

from gitlab_int.gitlab_client import (
    clip_text,
    get_gl,
    get_project,
    gl_call,
    list_bounded,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def _fmt_project(p: Any) -> dict:
    a = getattr(p, "attributes", {}) or {}
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "path_with_namespace": a.get("path_with_namespace"),
        "description": a.get("description"),
        "default_branch": a.get("default_branch"),
        "visibility": a.get("visibility"),
        "web_url": a.get("web_url"),
        "star_count": a.get("star_count"),
        "forks_count": a.get("forks_count"),
        "open_issues_count": a.get("open_issues_count"),
        "last_activity_at": a.get("last_activity_at"),
        "created_at": a.get("created_at"),
    }


def _fmt_commit(c: Any) -> dict:
    a = c if isinstance(c, dict) else (getattr(c, "attributes", {}) or {})
    return {
        "id": a.get("id"),
        "short_id": a.get("short_id"),
        "title": a.get("title"),
        "message": (a.get("message") or "").strip(),
        "author_name": a.get("author_name"),
        "author_email": a.get("author_email"),
        "created_at": a.get("created_at"),
        "committed_date": a.get("committed_date"),
        "web_url": a.get("web_url"),
        "parent_ids": a.get("parent_ids") or [],
        "stats": a.get("stats"),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@gl_call
def gitlab_project_list(search: str = "", limit: int = 50) -> dict:
    """
    TOOL: gitlab_project_list
    List projects the authenticated token can see (most recently active first).

    Parameters
    ----------
    search : str – optional name/path filter
    limit  : int – max projects to return (default 50)
    """
    gl = get_gl()
    kwargs: dict[str, Any] = {
        "membership": True,
        "order_by": "last_activity_at",
        "sort": "desc",
    }
    if search:
        kwargs["search"] = search
    projects = list_bounded(gl.projects, limit=limit, **kwargs)
    return {"count": len(projects), "projects": [_fmt_project(p) for p in projects]}


@gl_call
def gitlab_project_get(project_id: str) -> dict:
    """
    TOOL: gitlab_project_get
    Get details for a single project (id or 'namespace/path').
    """
    return _fmt_project(get_project(project_id))


@gl_call
def gitlab_project_create(
    name: str,
    namespace_id: str = "",
    path: str = "",
    visibility: str = "private",
    description: str = "",
    initialize_with_readme: bool = False,
    default_branch: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: gitlab_project_create
    Create a new project (repository). HUMAN-GATED — requires confirmed=True.

    Requires the token's user to have project-creation rights in the target
    namespace (their own namespace, or Developer/Maintainer on the group named
    by namespace_id, per the group's settings). If GitLab refuses, the caller
    gets an explicit "you don't have permission" error (HTTP 403).

    Parameters
    ----------
    name                   : str  – project display name
    namespace_id           : int  – group/user namespace id (blank = the token
                                    user's own personal namespace)
    path                   : str  – URL slug (defaults to a slug of `name`)
    visibility             : str  – private | internal | public (default private)
    description            : str
    initialize_with_readme : bool – seed an initial commit with a README
    default_branch         : str  – default branch name (needs a first commit)
    confirmed              : bool – must be True to actually create
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_project_create",
            "summary": f"Create project '{path or name}' ({visibility})",
            "reason": "Creating a project writes to GitLab — pass confirmed=True to execute.",
        }
    gl = get_gl()
    payload: dict[str, Any] = {"name": name, "visibility": visibility}
    if path:
        payload["path"] = path
    if namespace_id:
        payload["namespace_id"] = int(namespace_id)
    if description:
        payload["description"] = description
    if initialize_with_readme:
        payload["initialize_with_readme"] = True
    if default_branch:
        payload["default_branch"] = default_branch
    return _fmt_project(gl.projects.create(payload))


@gl_call
def gitlab_project_delete(project_id: str, confirmed: bool = False) -> dict:
    """
    TOOL: gitlab_project_delete
    Delete a project (repository). HUMAN-GATED — requires confirmed=True.

    Needs Owner on the project (or instance admin). GitLab returns an explicit
    permission error otherwise.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_project_delete",
            "summary": f"Permanently delete project {project_id}",
            "reason": "Deleting a project is irreversible — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    path = project.attributes.get("path_with_namespace")
    project.delete()
    return {"action": "gitlab_project_delete", "deleted": True, "project": path}


@gl_call
def gitlab_project_commits(project_id: str, ref: str = "", limit: int = 20) -> dict:
    """
    TOOL: gitlab_project_commits
    List the latest commits on a project (optionally for a specific branch/ref).

    Parameters
    ----------
    project_id : str – project id or 'namespace/path'
    ref        : str – branch name / tag / SHA (default: project default branch)
    limit      : int – number of commits (default 20)
    """
    project = get_project(project_id)
    kwargs: dict[str, Any] = {}
    if ref:
        kwargs["ref_name"] = ref
    commits = list_bounded(project.commits, limit=limit, **kwargs)
    return {
        "project": project.attributes.get("path_with_namespace"),
        "ref": ref or project.attributes.get("default_branch"),
        "count": len(commits),
        "commits": [_fmt_commit(c) for c in commits],
    }


@gl_call
def gitlab_commit_get(project_id: str, sha: str) -> dict:
    """
    TOOL: gitlab_commit_get
    Get a single commit with its stats (additions / deletions / total).
    """
    project = get_project(project_id)
    commit = project.commits.get(sha)
    return _fmt_commit(commit)


@gl_call
def gitlab_commit_diff(project_id: str, sha: str) -> dict:
    """
    TOOL: gitlab_commit_diff
    Get the diff a commit introduced (i.e. the change vs its parent commit).

    Returns the per-file diff plus a single concatenated 'text' blob suitable
    for feeding to the review agent ("previous commit → current commit").
    """
    project = get_project(project_id)
    commit = project.commits.get(sha)
    try:
        raw = commit.diff(get_all=True)
    except TypeError:
        raw = commit.diff(all=True)
    files = [
        {
            "old_path": d.get("old_path"),
            "new_path": d.get("new_path"),
            "new_file": d.get("new_file"),
            "deleted_file": d.get("deleted_file"),
            "renamed_file": d.get("renamed_file"),
            "diff": d.get("diff"),
        }
        for d in raw
    ]
    text = "\n".join(
        f"--- {f['old_path']}\n+++ {f['new_path']}\n{f['diff']}" for f in files if f.get("diff")
    )
    return {
        "project": project.attributes.get("path_with_namespace"),
        "sha": sha,
        "parent_ids": commit.attributes.get("parent_ids") or [],
        "file_count": len(files),
        "files": files,
        "text": clip_text(text),
    }


@gl_call
def gitlab_file_get(project_id: str, path: str, ref: str = "") -> dict:
    """
    TOOL: gitlab_file_get
    Read the raw text content of a file in a project at a ref.

    Parameters
    ----------
    project_id : str
    path       : str – file path in the repo, e.g. "src/app.py"
    ref        : str – branch / tag / SHA (default: project default branch)
    """
    project = get_project(project_id)
    ref = ref or project.attributes.get("default_branch") or "main"
    f = project.files.get(file_path=path.lstrip("/"), ref=ref)
    try:
        content = f.decode().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        content = f.attributes.get("content", "")
    return {
        "project": project.attributes.get("path_with_namespace"),
        "path": path,
        "ref": ref,
        "size": f.attributes.get("size"),
        "content": clip_text(content),
    }


@gl_call
def gitlab_compare(project_id: str, from_sha: str, to_sha: str) -> dict:
    """
    TOOL: gitlab_compare
    Compare two refs (branch names or SHAs) and return the commit list + diff.

    Useful to review a whole range: from_sha = previous known-good commit,
    to_sha = the new head.
    """
    project = get_project(project_id)
    result = project.repository_compare(from_sha, to_sha)
    diffs = result.get("diffs", []) if isinstance(result, dict) else getattr(result, "diffs", [])
    commits = result.get("commits", []) if isinstance(result, dict) else getattr(result, "commits", [])
    text = "\n".join(
        f"--- {d.get('old_path')}\n+++ {d.get('new_path')}\n{d.get('diff')}"
        for d in diffs
        if d.get("diff")
    )
    return {
        "project": project.attributes.get("path_with_namespace"),
        "from": from_sha,
        "to": to_sha,
        "commit_count": len(commits),
        "commits": [_fmt_commit(c) for c in commits],
        "file_count": len(diffs),
        "text": clip_text(text),
    }


# ---------------------------------------------------------------------------
# Dashboard helpers (not agent tools — used by gitlab_routes.dashboard)
# ---------------------------------------------------------------------------


def dashboard_projects(limit: int = 20) -> list[dict]:
    """Recently-active projects for the dashboard cards / selectors."""
    gl = get_gl()
    projects = list_bounded(
        gl.projects,
        limit=limit,
        membership=True,
        order_by="last_activity_at",
        sort="desc",
    )
    return [_fmt_project(p) for p in projects]


def get_latest_commits(limit: int = 10, scan_projects: int = 12) -> list[dict]:
    """Latest commits across recently-active projects, newest first (dashboard shape)."""
    gl = get_gl()
    projects = list_bounded(
        gl.projects,
        limit=scan_projects,
        membership=True,
        order_by="last_activity_at",
        sort="desc",
    )
    out: list[dict] = []
    for p in projects:
        path = p.attributes.get("path_with_namespace")
        try:
            commits = list_bounded(p.commits, limit=max(3, limit // 2))
        except Exception as exc:  # noqa: BLE001
            logger.warning("commits fetch failed for %s: %s", path, exc)
            continue
        for c in commits:
            a = c.attributes
            out.append(
                {
                    "hash": a.get("id"),
                    "short_id": a.get("short_id"),
                    "message": (a.get("title") or a.get("message") or "").strip(),
                    "author": a.get("author_name") or "unknown",
                    "email": a.get("author_email") or "",
                    "date": a.get("created_at") or a.get("committed_date"),
                    "web_url": a.get("web_url"),
                    "repo": path,
                }
            )
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    return out[:limit]
