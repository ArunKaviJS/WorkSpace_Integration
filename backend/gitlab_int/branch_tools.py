"""
gitlab_int/branch_tools.py
Branch tools — list / get / create / delete branches on a project.

``gitlab_branch_delete`` is HUMAN-GATED (requires confirmed=True).
"""
from __future__ import annotations

from typing import Any

from gitlab_int.gitlab_client import get_project, gl_call, list_bounded


def _fmt_branch(b: Any) -> dict:
    a = getattr(b, "attributes", {}) or {}
    commit = a.get("commit") or {}
    return {
        "name": a.get("name"),
        "default": a.get("default"),
        "protected": a.get("protected"),
        "merged": a.get("merged"),
        "web_url": a.get("web_url"),
        "commit": {
            "id": commit.get("id"),
            "short_id": commit.get("short_id"),
            "title": commit.get("title"),
            "author_name": commit.get("author_name"),
            "committed_date": commit.get("committed_date"),
        },
    }


@gl_call
def gitlab_branch_list(project_id: str, search: str = "", limit: int = 100) -> dict:
    """
    TOOL: gitlab_branch_list
    List branches on a project (optionally filtered by a search substring).
    """
    project = get_project(project_id)
    kwargs: dict[str, Any] = {}
    if search:
        kwargs["search"] = search
    branches = list_bounded(project.branches, limit=limit, **kwargs)
    return {
        "project": project.attributes.get("path_with_namespace"),
        "count": len(branches),
        "branches": [_fmt_branch(b) for b in branches],
    }


@gl_call
def gitlab_branch_get(project_id: str, branch: str) -> dict:
    """
    TOOL: gitlab_branch_get
    Get one branch on a project.
    """
    project = get_project(project_id)
    return _fmt_branch(project.branches.get(branch))


@gl_call
def gitlab_branch_create(
    project_id: str, branch: str, ref: str = "", confirmed: bool = False
) -> dict:
    """
    TOOL: gitlab_branch_create
    Create a branch from a ref (branch name / tag / SHA; defaults to the project
    default branch). HUMAN-GATED — requires confirmed=True.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_branch_create",
            "summary": f"Create branch '{branch}' in {project_id} from '{ref or 'default'}'",
            "reason": "Creating a branch writes to GitLab — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    ref = ref or project.attributes.get("default_branch") or "main"
    b = project.branches.create({"branch": branch, "ref": ref})
    return _fmt_branch(b)


@gl_call
def gitlab_branch_delete(project_id: str, branch: str, confirmed: bool = False) -> dict:
    """
    TOOL: gitlab_branch_delete
    Delete a branch. HUMAN-GATED — requires confirmed=True.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_branch_delete",
            "summary": f"Delete branch '{branch}' in {project_id}",
            "reason": "Deleting a branch is destructive — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    project.branches.delete(branch)
    return {"action": "gitlab_branch_delete", "deleted": True, "branch": branch}
