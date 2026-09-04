"""
gitlab_int/gitlab_routes.py
All backend API endpoints for the GitLab dashboard, chat and AI code review.

Mounted alongside the ClickUp and Bitbucket routers in backend/server.py.

Endpoints
---------
    POST /gitlab/chat                     — chat with the GitLab agent
    GET  /gitlab/me                       — authenticated user (gl.user)
    GET  /gitlab/dashboard               — summary + latest commits + pending MRs
    GET  /gitlab/commits                 — latest commits across active projects
    GET  /gitlab/pending-mrs            — all open MRs waiting for review

    GET  /gitlab/projects                — list projects
    GET  /gitlab/project                 — one project
    GET  /gitlab/project/commits         — commits on a project/ref
    GET  /gitlab/project/file            — raw file content
    GET  /gitlab/compare                 — diff between two refs
    GET  /gitlab/commit                  — one commit
    GET  /gitlab/commit/diff             — diff a commit introduced

    GET  /gitlab/branches                — list branches
    GET  /gitlab/branch                  — one branch
    POST /gitlab/branch/create           — create branch
    POST /gitlab/branch/delete           — human-confirmed delete

    GET  /gitlab/mrs                     — list merge requests
    GET  /gitlab/mr                      — one merge request
    GET  /gitlab/mr/changes             — full MR diff
    GET  /gitlab/mr/notes               — MR comments
    POST /gitlab/mr/note                — add a comment
    POST /gitlab/mr/create             — open an MR
    POST /gitlab/mr/approve            — human-confirmed approve
    POST /gitlab/mr/unapprove          — human-confirmed unapprove
    POST /gitlab/mr/merge             — human-confirmed merge
    POST /gitlab/mr/close            — human-confirmed close

    GET  /gitlab/mr/review             — AI review of a merge request
    GET  /gitlab/commit/review         — AI review of one commit vs its parent
    GET  /gitlab/review/compare        — AI review of a from..to range

    GET  /gitlab/pipelines / /gitlab/pipeline / /gitlab/pipeline/jobs

All errors are returned as {"error": "<message>"} (same shape as the other routers).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from gitlab_int.branch_tools import (
    gitlab_branch_create,
    gitlab_branch_delete,
    gitlab_branch_get,
    gitlab_branch_list,
)
from gitlab_int.gitlab_agent import GitLabAgent
from gitlab_int.gitlab_client import current_user
from gitlab_int.gitlab_prompts import summarize_pending_mr
from gitlab_int.gitlab_time_utils import format_commits
from gitlab_int.mr_tools import (
    gitlab_mr_approve,
    gitlab_mr_changes,
    gitlab_mr_close,
    gitlab_mr_create,
    gitlab_mr_get,
    gitlab_mr_list,
    gitlab_mr_merge,
    gitlab_mr_note_add,
    gitlab_mr_notes_list,
    gitlab_mr_unapprove,
    get_pending_mrs,
)
from gitlab_int.pipeline_tools import (
    gitlab_pipeline_get,
    gitlab_pipeline_jobs,
    gitlab_pipeline_list,
)
from gitlab_int.project_tools import (
    dashboard_projects,
    get_latest_commits,
    gitlab_commit_diff,
    gitlab_commit_get,
    gitlab_compare,
    gitlab_file_get,
    gitlab_project_commits,
    gitlab_project_create,
    gitlab_project_delete,
    gitlab_project_get,
    gitlab_project_list,
)
from gitlab_int.review_agent import (
    gitlab_review_commit,
    gitlab_review_commit_range,
    gitlab_review_merge_request,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gitlab")

_agent: GitLabAgent | None = None


def get_agent() -> GitLabAgent:
    global _agent
    if _agent is None:
        _agent = GitLabAgent()
    return _agent


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatIn(BaseModel):
    message: str


class NoteIn(BaseModel):
    project_id: str
    mr_iid: int
    body: str
    confirmed: bool = False


class MrCreateIn(BaseModel):
    project_id: str
    source_branch: str
    target_branch: str
    title: str
    description: str = ""
    remove_source_branch: bool = False
    confirmed: bool = False


class MrActionIn(BaseModel):
    project_id: str
    mr_iid: int
    confirmed: bool = False


class MrMergeIn(BaseModel):
    project_id: str
    mr_iid: int
    merge_commit_message: str = ""
    squash: bool = False
    remove_source_branch: bool = False
    merge_when_pipeline_succeeds: bool = False
    confirmed: bool = False


class ProjectCreateIn(BaseModel):
    name: str
    namespace_id: int | None = None
    path: str = ""
    visibility: str = "private"
    description: str = ""
    initialize_with_readme: bool = False
    default_branch: str = ""
    confirmed: bool = False


class ProjectDeleteIn(BaseModel):
    project_id: str
    confirmed: bool = False


class BranchCreateIn(BaseModel):
    project_id: str
    branch: str
    ref: str = ""
    confirmed: bool = False


class BranchDeleteIn(BaseModel):
    project_id: str
    branch: str
    confirmed: bool = False


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


@router.post("/chat")
def chat(body: ChatIn) -> dict:
    try:
        reply = get_agent().run(body.message)
        return {"reply": reply, "tool_calls": get_agent().tool_calls_log}
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitLab chat failed")
        return {"reply": f"Agent error: {exc}", "tool_calls": []}


@router.post("/chat/reset")
def chat_reset() -> dict:
    get_agent().reset()
    return {"status": "reset"}


@router.get("/me")
def me() -> dict:
    try:
        return current_user()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
def dashboard() -> dict:
    try:
        commits = format_commits(get_latest_commits(limit=10))
        pending = get_pending_mrs()
        projects = dashboard_projects(limit=25)
        return {
            "projects": projects,
            "commits": commits,
            "pending_mrs": pending,
            "summary": {
                "total_projects": len(projects),
                "open_mrs": len(pending),
                "recent_commits": len(commits),
            },
            "generated_at": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitLab dashboard build failed")
        return {"error": str(exc)}


@router.get("/commits")
def commits() -> dict:
    try:
        items = format_commits(get_latest_commits(limit=15))
        return {"commits": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/pending-mrs")
def pending_mrs() -> dict:
    try:
        items = get_pending_mrs()
        for mr in items:
            mr["summary"] = summarize_pending_mr(mr)
        return {"pending_mrs": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Projects / commits / files
# ---------------------------------------------------------------------------


@router.get("/projects")
def projects(search: str = "", limit: int = 50) -> dict:
    try:
        return gitlab_project_list(search=search, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/project")
def project(project_id: str) -> dict:
    try:
        return gitlab_project_get(project_id=project_id)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/project/create")
def project_create(body: ProjectCreateIn) -> dict:
    try:
        return gitlab_project_create(
            name=body.name,
            namespace_id=str(body.namespace_id) if body.namespace_id else "",
            path=body.path,
            visibility=body.visibility,
            description=body.description,
            initialize_with_readme=body.initialize_with_readme,
            default_branch=body.default_branch,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/project/delete")
def project_delete(body: ProjectDeleteIn) -> dict:
    try:
        return gitlab_project_delete(project_id=body.project_id, confirmed=body.confirmed)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/project/commits")
def project_commits(project_id: str, ref: str = "", limit: int = 20) -> dict:
    try:
        return gitlab_project_commits(project_id=project_id, ref=ref, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/project/file")
def project_file(project_id: str, path: str, ref: str = "") -> dict:
    try:
        return gitlab_file_get(project_id=project_id, path=path, ref=ref)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/compare")
def compare(project_id: str, from_sha: str, to_sha: str) -> dict:
    try:
        return gitlab_compare(project_id=project_id, from_sha=from_sha, to_sha=to_sha)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/commit")
def commit(project_id: str, sha: str) -> dict:
    try:
        return gitlab_commit_get(project_id=project_id, sha=sha)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/commit/diff")
def commit_diff(project_id: str, sha: str) -> dict:
    try:
        return gitlab_commit_diff(project_id=project_id, sha=sha)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------


@router.get("/branches")
def branches(project_id: str, search: str = "", limit: int = 100) -> dict:
    try:
        return gitlab_branch_list(project_id=project_id, search=search, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/branch")
def branch(project_id: str, branch: str) -> dict:
    try:
        return gitlab_branch_get(project_id=project_id, branch=branch)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/branch/create")
def branch_create(body: BranchCreateIn) -> dict:
    try:
        return gitlab_branch_create(
            project_id=body.project_id,
            branch=body.branch,
            ref=body.ref,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/branch/delete")
def branch_delete(body: BranchDeleteIn) -> dict:
    try:
        return gitlab_branch_delete(
            project_id=body.project_id, branch=body.branch, confirmed=body.confirmed
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Merge requests
# ---------------------------------------------------------------------------


@router.get("/mrs")
def mrs(project_id: str, state: str = "opened", limit: int = 50) -> dict:
    try:
        return gitlab_mr_list(project_id=project_id, state=state, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/mr")
def mr(project_id: str, mr_iid: int) -> dict:
    try:
        return gitlab_mr_get(project_id=project_id, mr_iid=mr_iid)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/mr/changes")
def mr_changes(project_id: str, mr_iid: int) -> dict:
    try:
        return gitlab_mr_changes(project_id=project_id, mr_iid=mr_iid)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/mr/notes")
def mr_notes(project_id: str, mr_iid: int, limit: int = 50) -> dict:
    try:
        return gitlab_mr_notes_list(project_id=project_id, mr_iid=mr_iid, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/mr/note")
def mr_note(body: NoteIn) -> dict:
    try:
        return gitlab_mr_note_add(
            project_id=body.project_id,
            mr_iid=body.mr_iid,
            body=body.body,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/mr/create")
def mr_create(body: MrCreateIn) -> dict:
    try:
        return gitlab_mr_create(
            project_id=body.project_id,
            source_branch=body.source_branch,
            target_branch=body.target_branch,
            title=body.title,
            description=body.description,
            remove_source_branch=body.remove_source_branch,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/mr/approve")
def mr_approve(body: MrActionIn) -> dict:
    try:
        return gitlab_mr_approve(
            project_id=body.project_id, mr_iid=body.mr_iid, confirmed=body.confirmed
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/mr/unapprove")
def mr_unapprove(body: MrActionIn) -> dict:
    try:
        return gitlab_mr_unapprove(
            project_id=body.project_id, mr_iid=body.mr_iid, confirmed=body.confirmed
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/mr/merge")
def mr_merge(body: MrMergeIn) -> dict:
    try:
        return gitlab_mr_merge(
            project_id=body.project_id,
            mr_iid=body.mr_iid,
            merge_commit_message=body.merge_commit_message,
            squash=body.squash,
            remove_source_branch=body.remove_source_branch,
            merge_when_pipeline_succeeds=body.merge_when_pipeline_succeeds,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.post("/mr/close")
def mr_close(body: MrActionIn) -> dict:
    try:
        return gitlab_mr_close(
            project_id=body.project_id, mr_iid=body.mr_iid, confirmed=body.confirmed
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# AI code review (dedicated agent)
# ---------------------------------------------------------------------------


@router.get("/mr/review")
def mr_review(project_id: str, mr_iid: int) -> dict:
    try:
        return gitlab_review_merge_request(project_id=project_id, mr_iid=mr_iid)
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitLab MR review failed")
        return {"error": str(exc)}


@router.get("/commit/review")
def commit_review(project_id: str, sha: str) -> dict:
    try:
        return gitlab_review_commit(project_id=project_id, sha=sha)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/review/compare")
def review_compare(project_id: str, from_sha: str, to_sha: str) -> dict:
    try:
        return gitlab_review_commit_range(
            project_id=project_id, from_sha=from_sha, to_sha=to_sha
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------


@router.get("/pipelines")
def pipelines(project_id: str, ref: str = "", limit: int = 20) -> dict:
    try:
        return gitlab_pipeline_list(project_id=project_id, ref=ref, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/pipeline")
def pipeline(project_id: str, pipeline_id: int) -> dict:
    try:
        return gitlab_pipeline_get(project_id=project_id, pipeline_id=pipeline_id)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/pipeline/jobs")
def pipeline_jobs(project_id: str, pipeline_id: int, limit: int = 50) -> dict:
    try:
        return gitlab_pipeline_jobs(
            project_id=project_id, pipeline_id=pipeline_id, limit=limit
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
