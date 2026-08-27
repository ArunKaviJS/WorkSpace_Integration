"""
bitbucket/bitbucket_routes.py
All backend API endpoints for the Bitbucket dashboard and chat.

Routing pattern mirrors backend/server.py for ClickUp, but this module exposes
an APIRouter so it can be mounted alongside (or independently of) the ClickUp
server without touching any ClickUp logic.

Endpoints
---------
    POST /bitbucket/chat                     — chat with the Bitbucket agent
    GET  /bitbucket/dashboard                — dashboard data (commits, PRs)
    GET  /bitbucket/commits                  — latest 10 commits per repo
    GET  /bitbucket/pending-prs              — all open PRs waiting for review
    POST /bitbucket/pr/approve               — human-confirmed approve
    POST /bitbucket/pr/decline               — human-confirmed decline
    POST /bitbucket/pr/merge                 — human-confirmed merge
    POST /bitbucket/repo/create              — create repo
    POST /bitbucket/repo/delete              — human-confirmed delete
    POST /bitbucket/branch/create            — create branch
    POST /bitbucket/branch/permission        — set branch permissions
    POST /bitbucket/collaborator/invite      — invite collaborator

All errors are returned in the same format the ClickUp routes use:
    {"error": "<message>"}
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from bitbucket.bitbucket_agent import BitbucketAgent
from bitbucket.bitbucket_prompts import summarize_pending_pr
from bitbucket.bitbucket_time_utils import format_commits
from bitbucket.bitbucket_tools import (
    approve_pr,
    create_branch,
    create_repo,
    decline_pr,
    delete_repo,
    get_latest_commits,
    get_pending_prs,
    invite_collaborator,
    list_repos,
    merge_pr,
    set_branch_permission,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bitbucket")

# One shared Bitbucket chat agent instance per server process.
_agent: BitbucketAgent | None = None


def get_agent() -> BitbucketAgent:
    """Lazily create (and reuse) a single Bitbucket agent instance."""
    global _agent
    if _agent is None:
        _agent = BitbucketAgent()
    return _agent


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatIn(BaseModel):
    message: str


class ApproveIn(BaseModel):
    workspace: str = ""
    repo_slug: str
    pr_id: int
    confirmed: bool = False


class DeclineIn(BaseModel):
    workspace: str = ""
    repo_slug: str
    pr_id: int
    confirmed: bool = False


class MergeIn(BaseModel):
    workspace: str = ""
    repo_slug: str
    pr_id: int
    merge_strategy: str = "merge_commit"
    confirmed: bool = False


class RepoCreateIn(BaseModel):
    workspace: str = ""
    repo_name: str
    is_private: bool = True
    description: str = ""


class RepoDeleteIn(BaseModel):
    workspace: str = ""
    repo_slug: str
    confirmed: bool = False


class BranchCreateIn(BaseModel):
    workspace: str = ""
    repo_slug: str
    branch_name: str
    from_commit: str = ""


class BranchPermissionIn(BaseModel):
    workspace: str = ""
    repo_slug: str
    branch_pattern: str
    kind: str
    value: str = ""
    confirmed: bool = False


class InviteIn(BaseModel):
    workspace: str = ""
    repo_slug: str
    email_or_uuid: str
    role: str = "write"


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


@router.post("/chat")
def chat(body: ChatIn) -> dict:
    """Send a user message to the Bitbucket agent; returns the final reply."""
    try:
        reply = get_agent().run(body.message)
        return {"reply": reply, "tool_calls": get_agent().tool_calls_log}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket chat failed")
        return {"reply": f"Agent error: {exc}", "tool_calls": []}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
def dashboard() -> dict:
    """Dashboard data: summary cards, latest commits and pending PRs."""
    try:
        commits = format_commits(get_latest_commits(limit=10))
        pending_prs = get_pending_prs()
        repos = list_repos()

        return {
            "repos": repos,
            "commits": commits,
            "pending_prs": pending_prs,
            "summary": {
                "total_repos": len(repos),
                "open_prs": len(pending_prs),
                "recent_commits": len(commits),
            },
            "generated_at": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket dashboard build failed")
        return {"error": str(exc)}


@router.get("/commits")
def commits() -> dict:
    """Latest 10 commits per repo with author info."""
    try:
        items = format_commits(get_latest_commits(limit=10))
        return {"commits": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket commits failed")
        return {"error": str(exc)}


@router.get("/pending-prs")
def pending_prs() -> dict:
    """All open PRs waiting for review with waiting-time info."""
    try:
        items = get_pending_prs()
        for pr in items:
            pr["summary"] = summarize_pending_pr(pr)
        return {"pending_prs": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket pending PRs failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Human-gated PR actions
# ---------------------------------------------------------------------------


@router.post("/pr/approve")
def pr_approve(body: ApproveIn) -> dict:
    try:
        return approve_pr(
            workspace=body.workspace,
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket approve PR failed")
        return {"error": str(exc)}


@router.post("/pr/decline")
def pr_decline(body: DeclineIn) -> dict:
    try:
        return decline_pr(
            workspace=body.workspace,
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket decline PR failed")
        return {"error": str(exc)}


@router.post("/pr/merge")
def pr_merge(body: MergeIn) -> dict:
    try:
        return merge_pr(
            workspace=body.workspace,
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            merge_strategy=body.merge_strategy,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket merge PR failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Repo / branch / collaborator actions
# ---------------------------------------------------------------------------


@router.post("/repo/create")
def repo_create(body: RepoCreateIn) -> dict:
    try:
        return create_repo(
            repo_name=body.repo_name,
            workspace=body.workspace,
            is_private=body.is_private,
            description=body.description,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket create repo failed")
        return {"error": str(exc)}


@router.post("/repo/delete")
def repo_delete(body: RepoDeleteIn) -> dict:
    try:
        return delete_repo(
            repo_slug=body.repo_slug,
            workspace=body.workspace,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket delete repo failed")
        return {"error": str(exc)}


@router.post("/branch/create")
def branch_create(body: BranchCreateIn) -> dict:
    try:
        return create_branch(
            repo_slug=body.repo_slug,
            branch_name=body.branch_name,
            from_commit=body.from_commit,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket create branch failed")
        return {"error": str(exc)}


@router.post("/branch/permission")
def branch_permission(body: BranchPermissionIn) -> dict:
    try:
        return set_branch_permission(
            repo_slug=body.repo_slug,
            branch_pattern=body.branch_pattern,
            kind=body.kind,
            value=body.value,
            workspace=body.workspace,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket set branch permission failed")
        return {"error": str(exc)}


@router.post("/collaborator/invite")
def collaborator_invite(body: InviteIn) -> dict:
    try:
        return invite_collaborator(
            repo_slug=body.repo_slug,
            email_or_uuid=body.email_or_uuid,
            role=body.role,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket invite collaborator failed")
        return {"error": str(exc)}
