"""
gitlab_int/mr_tools.py
Merge-request tools — list / get / changes(diff) / notes / create, plus the
reviewer actions (approve, unapprove, merge, close).

Reviewer actions that change state (approve, merge, close) are HUMAN-GATED:
they require an explicit ``confirmed=True`` flag before they run, so the agent
can never act on an MR without the user's confirmation. This mirrors the
Bitbucket PR tools.
"""
from __future__ import annotations

import logging
from typing import Any

from gitlab_int.gitlab_client import clip_text, get_gl, get_project, gl_call, list_bounded

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def _fmt_mr(mr: Any) -> dict:
    a = mr if isinstance(mr, dict) else (getattr(mr, "attributes", {}) or {})
    author = a.get("author") or {}
    return {
        "iid": a.get("iid"),
        "id": a.get("id"),
        "project_id": a.get("project_id"),
        "title": a.get("title"),
        "description": a.get("description"),
        "state": a.get("state"),
        "draft": a.get("draft", a.get("work_in_progress")),
        "merge_status": a.get("merge_status"),
        "detailed_merge_status": a.get("detailed_merge_status"),
        "has_conflicts": a.get("has_conflicts"),
        "author": author.get("name") or author.get("username") or "",
        "source_branch": a.get("source_branch"),
        "target_branch": a.get("target_branch"),
        "created_at": a.get("created_at"),
        "updated_at": a.get("updated_at"),
        "web_url": a.get("web_url"),
        "upvotes": a.get("upvotes"),
        "user_notes_count": a.get("user_notes_count"),
        "sha": a.get("sha"),
    }


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@gl_call
def gitlab_mr_list(project_id: str, state: str = "opened", limit: int = 50) -> dict:
    """
    TOOL: gitlab_mr_list
    List merge requests for a project.

    Parameters
    ----------
    project_id : str – id or 'namespace/path'
    state      : str – opened | closed | merged | locked | all (default opened)
    limit      : int – page size (default 50)
    """
    project = get_project(project_id)
    kwargs: dict[str, Any] = {"order_by": "updated_at", "sort": "desc"}
    if state and state != "all":
        kwargs["state"] = state
    mrs = list_bounded(project.mergerequests, limit=limit, **kwargs)
    return {
        "project": project.attributes.get("path_with_namespace"),
        "state": state,
        "count": len(mrs),
        "merge_requests": [_fmt_mr(m) for m in mrs],
    }


@gl_call
def gitlab_mr_get(project_id: str, mr_iid: int) -> dict:
    """
    TOOL: gitlab_mr_get
    Get one merge request (by its project-scoped iid) with approval info when available.
    """
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)
    out = _fmt_mr(mr)
    try:
        ap = mr.approvals.get()
        out["approvals"] = {
            "approved": ap.attributes.get("approved"),
            "approvals_required": ap.attributes.get("approvals_required"),
            "approvals_left": ap.attributes.get("approvals_left"),
            "approved_by": [
                (x.get("user") or {}).get("username")
                for x in (ap.attributes.get("approved_by") or [])
            ],
        }
    except Exception:  # noqa: BLE001 - approvals API is Premium; degrade gracefully
        out["approvals"] = None
    return out


@gl_call
def gitlab_mr_changes(project_id: str, mr_iid: int) -> dict:
    """
    TOOL: gitlab_mr_changes
    Get the full diff of a merge request (all changed files) plus the base /
    head SHAs. This is what the review agent consumes.
    """
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)

    changes: list[dict] = []
    diff_refs: dict = {}
    try:
        data = mr.changes()
        changes = data.get("changes", []) or []
        diff_refs = data.get("diff_refs") or {}
    except Exception:  # noqa: BLE001 - mr.changes() deprecated on newer SDKs
        try:
            for d in mr.diffs.list(iterator=True):
                da = getattr(d, "attributes", {}) or {}
                changes.append(da)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mr changes fallback failed: %s", exc)
        diff_refs = mr.attributes.get("diff_refs") or {}

    files = [
        {
            "old_path": c.get("old_path"),
            "new_path": c.get("new_path"),
            "new_file": c.get("new_file"),
            "deleted_file": c.get("deleted_file"),
            "renamed_file": c.get("renamed_file"),
            "diff": c.get("diff"),
        }
        for c in changes
    ]
    text = "\n".join(
        f"--- {f['old_path']}\n+++ {f['new_path']}\n{f['diff']}" for f in files if f.get("diff")
    )
    return {
        "project": project.attributes.get("path_with_namespace"),
        "mr_iid": mr_iid,
        "title": mr.attributes.get("title"),
        "description": mr.attributes.get("description"),
        "author": (mr.attributes.get("author") or {}).get("name"),
        "source_branch": mr.attributes.get("source_branch"),
        "target_branch": mr.attributes.get("target_branch"),
        "base_sha": diff_refs.get("base_sha"),
        "start_sha": diff_refs.get("start_sha"),
        "head_sha": diff_refs.get("head_sha"),
        "file_count": len(files),
        "files": files,
        "text": clip_text(text),
    }


@gl_call
def gitlab_mr_notes_list(project_id: str, mr_iid: int, limit: int = 50) -> dict:
    """
    TOOL: gitlab_mr_notes_list
    List discussion notes (comments) on a merge request, newest first.
    """
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)
    notes = list_bounded(mr.notes, limit=limit, order_by="created_at", sort="desc")
    return {
        "project": project.attributes.get("path_with_namespace"),
        "mr_iid": mr_iid,
        "count": len(notes),
        "notes": [
            {
                "id": n.attributes.get("id"),
                "author": (n.attributes.get("author") or {}).get("name"),
                "body": n.attributes.get("body"),
                "system": n.attributes.get("system"),
                "created_at": n.attributes.get("created_at"),
            }
            for n in notes
        ],
    }


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


@gl_call
def gitlab_mr_note_add(
    project_id: str, mr_iid: int, body: str, confirmed: bool = False
) -> dict:
    """
    TOOL: gitlab_mr_note_add
    Post a comment / review note on a merge request.
    HUMAN-GATED — requires confirmed=True.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_mr_note_add",
            "summary": f"Post a comment on MR !{mr_iid} in {project_id}",
            "reason": "Posting a comment writes to GitLab — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)
    note = mr.notes.create({"body": body})
    return {
        "id": note.attributes.get("id"),
        "body": note.attributes.get("body"),
        "created_at": note.attributes.get("created_at"),
    }


@gl_call
def gitlab_mr_create(
    project_id: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str = "",
    remove_source_branch: bool = False,
    confirmed: bool = False,
) -> dict:
    """
    TOOL: gitlab_mr_create
    Open a new merge request. HUMAN-GATED — requires confirmed=True.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_mr_create",
            "summary": f"Open MR '{title}' ({source_branch} → {target_branch}) in {project_id}",
            "reason": "Creating a merge request writes to GitLab — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    payload: dict[str, Any] = {
        "source_branch": source_branch,
        "target_branch": target_branch or project.attributes.get("default_branch") or "main",
        "title": title,
        "remove_source_branch": bool(remove_source_branch),
    }
    if description:
        payload["description"] = description
    mr = project.mergerequests.create(payload)
    return _fmt_mr(mr)


@gl_call
def gitlab_mr_approve(project_id: str, mr_iid: int, confirmed: bool = False) -> dict:
    """
    TOOL: gitlab_mr_approve
    Approve a merge request. HUMAN-GATED — requires confirmed=True.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_mr_approve",
            "summary": f"Approve merge request !{mr_iid} in {project_id}",
            "reason": "Approving an MR is a review action — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)
    try:
        mr.approve()
    except Exception as exc:  # noqa: BLE001
        return {
            "action": "gitlab_mr_approve",
            "approved": False,
            "mr_iid": mr_iid,
            "note": (
                "Approve call failed — the MR Approvals API needs GitLab Premium/Ultimate. "
                f"({exc}) Use a review note instead."
            ),
        }
    return {"action": "gitlab_mr_approve", "approved": True, "mr_iid": mr_iid}


@gl_call
def gitlab_mr_unapprove(project_id: str, mr_iid: int, confirmed: bool = False) -> dict:
    """
    TOOL: gitlab_mr_unapprove
    Revoke your approval on a merge request. HUMAN-GATED — requires confirmed=True.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_mr_unapprove",
            "summary": f"Revoke approval on merge request !{mr_iid} in {project_id}",
            "reason": "Pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)
    try:
        mr.unapprove()
    except Exception as exc:  # noqa: BLE001
        return {"action": "gitlab_mr_unapprove", "unapproved": False, "note": str(exc)}
    return {"action": "gitlab_mr_unapprove", "unapproved": True, "mr_iid": mr_iid}


@gl_call
def gitlab_mr_merge(
    project_id: str,
    mr_iid: int,
    merge_commit_message: str = "",
    squash: bool = False,
    remove_source_branch: bool = False,
    merge_when_pipeline_succeeds: bool = False,
    confirmed: bool = False,
) -> dict:
    """
    TOOL: gitlab_mr_merge
    Merge a merge request. HUMAN-GATED — requires confirmed=True.

    Parameters
    ----------
    merge_commit_message         : str  – optional custom merge commit message
    squash                       : bool – squash commits on merge
    remove_source_branch         : bool – delete the source branch after merge
    merge_when_pipeline_succeeds  : bool – queue the merge for a green pipeline
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_mr_merge",
            "summary": f"Merge merge request !{mr_iid} in {project_id}",
            "reason": "Merging an MR is a destructive action — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)
    kwargs: dict[str, Any] = {
        "squash": bool(squash),
        "should_remove_source_branch": bool(remove_source_branch),
    }
    if merge_commit_message:
        kwargs["merge_commit_message"] = merge_commit_message
    if merge_when_pipeline_succeeds:
        kwargs["merge_when_pipeline_succeeds"] = True
    mr.merge(**kwargs)
    fresh = project.mergerequests.get(mr_iid)
    return {
        "action": "gitlab_mr_merge",
        "merged": fresh.attributes.get("state") == "merged",
        "state": fresh.attributes.get("state"),
        "mr_iid": mr_iid,
        "merge_commit_sha": fresh.attributes.get("merge_commit_sha"),
    }


@gl_call
def gitlab_mr_close(project_id: str, mr_iid: int, confirmed: bool = False) -> dict:
    """
    TOOL: gitlab_mr_close
    Close (decline) a merge request without merging. HUMAN-GATED — requires confirmed=True.
    """
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "gitlab_mr_close",
            "summary": f"Close merge request !{mr_iid} in {project_id}",
            "reason": "Closing an MR is a review action — pass confirmed=True to execute.",
        }
    project = get_project(project_id)
    mr = project.mergerequests.get(mr_iid)
    mr.state_event = "close"
    mr.save()
    return {"action": "gitlab_mr_close", "closed": True, "mr_iid": mr_iid}


# ---------------------------------------------------------------------------
# Dashboard helper (not an agent tool)
# ---------------------------------------------------------------------------


def get_pending_mrs(scan_projects: int = 20) -> list[dict]:
    """All OPEN merge requests across recently-active projects (dashboard shape)."""
    gl = get_gl()
    projects = list_bounded(
        gl.projects,
        limit=scan_projects,
        membership=True,
        order_by="last_activity_at",
        sort="desc",
    )
    pending: list[dict] = []
    for p in projects:
        path = p.attributes.get("path_with_namespace")
        try:
            mrs = list_bounded(p.mergerequests, limit=50, state="opened")
        except Exception as exc:  # noqa: BLE001
            logger.warning("MR fetch failed for %s: %s", path, exc)
            continue
        for m in mrs:
            f = _fmt_mr(m)
            f["repo"] = path
            f["project"] = path
            f["created_on"] = f.get("created_at")
            pending.append(f)
    pending.sort(key=lambda x: x.get("created_on") or "", reverse=True)
    return pending
