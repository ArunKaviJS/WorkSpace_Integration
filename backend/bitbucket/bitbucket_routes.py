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
from bitbucket.deployment_tools import (
    bitbucket_deployment_get,
    bitbucket_deployment_list,
    bitbucket_environment_create,
    bitbucket_environment_delete,
    bitbucket_environment_get,
    bitbucket_environment_list,
    bitbucket_environment_update,
)
from bitbucket.pipeline_tools import (
    bitbucket_analyze_pipeline_step_failure,
    bitbucket_analyze_pr_commit_failures,
    bitbucket_pipeline_get,
    bitbucket_pipeline_list,
    bitbucket_pipeline_run,
    bitbucket_pipeline_step_get,
    bitbucket_pipeline_step_log,
    bitbucket_pipeline_steps,
)
from bitbucket.pr_tools import (
    bitbucket_pr_approve,
    bitbucket_pr_comment_add,
    bitbucket_pr_comment_list,
    bitbucket_pr_comment_update,
    bitbucket_pr_create,
    bitbucket_pr_decline,
    bitbucket_pr_diff,
    bitbucket_pr_get,
    bitbucket_pr_list,
    bitbucket_pr_merge,
    bitbucket_pr_task_create,
    bitbucket_pr_task_list,
    bitbucket_pr_task_update,
    bitbucket_user_pull_requests,
)
from bitbucket.repos_tools import (
    bitbucket_repo_branch_create,
    bitbucket_repo_branch_get,
    bitbucket_repo_commit_create,
    bitbucket_repo_commit_get,
    bitbucket_repo_default_reviewers,
    bitbucket_repo_files_get,
    bitbucket_repo_get,
    bitbucket_repo_list,
)
from bitbucket.workspace_tools import (
    bitbucket_workspace_get,
    bitbucket_workspace_list,
)
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


# ---------------------------------------------------------------------------
# Workspaces (bitbucket_*) — new tools
# ---------------------------------------------------------------------------


@router.get("/workspaces")
def bb_workspace_list() -> dict:
    try:
        return bitbucket_workspace_list()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket workspace list failed")
        return {"error": str(exc)}


@router.get("/workspace")
def bb_workspace_get(workspace: str = "") -> dict:
    try:
        return bitbucket_workspace_get(workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket workspace get failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Repositories (bitbucket_*) — new tools
# ---------------------------------------------------------------------------


@router.get("/repos")
def bb_repo_list(workspace: str = "") -> dict:
    try:
        return bitbucket_repo_list(workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket repo list failed")
        return {"error": str(exc)}


@router.get("/repo")
def bb_repo_get(repo_slug: str, workspace: str = "") -> dict:
    try:
        return bitbucket_repo_get(repo_slug=repo_slug, workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket repo get failed")
        return {"error": str(exc)}


@router.get("/repo/default-reviewers")
def bb_repo_default_reviewers(repo_slug: str, workspace: str = "") -> dict:
    try:
        return bitbucket_repo_default_reviewers(repo_slug=repo_slug, workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket default reviewers failed")
        return {"error": str(exc)}


@router.get("/repo/file")
def bb_repo_file(repo_slug: str, path: str, revision: str = "", workspace: str = "") -> dict:
    try:
        return bitbucket_repo_files_get(
            repo_slug=repo_slug, path=path, revision=revision, workspace=workspace
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket file get failed")
        return {"error": str(exc)}


@router.get("/repo/commit")
def bb_repo_commit_get(repo_slug: str, revision: str = "", workspace: str = "") -> dict:
    try:
        return bitbucket_repo_commit_get(
            repo_slug=repo_slug, revision=revision, workspace=workspace
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket commit get failed")
        return {"error": str(exc)}


class CommitCreateIn(BaseModel):
    repo_slug: str
    file_path: str
    content: str
    message: str
    branch: str = ""
    workspace: str = ""


@router.post("/repo/commit")
def bb_repo_commit_create(body: CommitCreateIn) -> dict:
    try:
        return bitbucket_repo_commit_create(
            repo_slug=body.repo_slug,
            file_path=body.file_path,
            content=body.content,
            message=body.message,
            branch=body.branch,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket commit create failed")
        return {"error": str(exc)}


@router.get("/repo/branch")
def bb_repo_branch_get(repo_slug: str, branch_name: str, workspace: str = "") -> dict:
    try:
        return bitbucket_repo_branch_get(
            repo_slug=repo_slug, branch_name=branch_name, workspace=workspace
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket branch get failed")
        return {"error": str(exc)}


class BranchCreateNewIn(BaseModel):
    repo_slug: str
    branch_name: str
    from_commit: str = ""
    workspace: str = ""


@router.post("/repo/branch")
def bb_repo_branch_create(body: BranchCreateNewIn) -> dict:
    try:
        return bitbucket_repo_branch_create(
            repo_slug=body.repo_slug,
            branch_name=body.branch_name,
            from_commit=body.from_commit,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket branch create failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Pull requests (bitbucket_*) — new tools
# ---------------------------------------------------------------------------


class PrCreateIn(BaseModel):
    repo_slug: str
    title: str
    source_branch: str = ""
    destination_branch: str = ""
    description: str = ""
    workspace: str = ""


@router.get("/pr/list")
def bb_pr_list(repo_slug: str, state: str = "OPEN", workspace: str = "", pagelen: int = 50) -> dict:
    try:
        return bitbucket_pr_list(
            repo_slug=repo_slug, state=state, workspace=workspace, pagelen=pagelen
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR list failed")
        return {"error": str(exc)}


@router.post("/pr/create")
def bb_pr_create(body: PrCreateIn) -> dict:
    try:
        return bitbucket_pr_create(
            repo_slug=body.repo_slug,
            title=body.title,
            source_branch=body.source_branch,
            destination_branch=body.destination_branch,
            description=body.description,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR create failed")
        return {"error": str(exc)}


@router.get("/pr")
def bb_pr_get(repo_slug: str, pr_id: int, workspace: str = "") -> dict:
    try:
        return bitbucket_pr_get(repo_slug=repo_slug, pr_id=pr_id, workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR get failed")
        return {"error": str(exc)}


@router.get("/pr/diff")
def bb_pr_diff(repo_slug: str, pr_id: int, workspace: str = "") -> dict:
    try:
        return bitbucket_pr_diff(repo_slug=repo_slug, pr_id=pr_id, workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR diff failed")
        return {"error": str(exc)}


class PrMergeIn(BaseModel):
    repo_slug: str
    pr_id: int
    merge_strategy: str = "merge_commit"
    workspace: str = ""
    confirmed: bool = False


@router.post("/pr/merge")
def bb_pr_merge(body: PrMergeIn) -> dict:
    try:
        return bitbucket_pr_merge(
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            merge_strategy=body.merge_strategy,
            workspace=body.workspace,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR merge failed")
        return {"error": str(exc)}


@router.get("/pr/comments")
def bb_pr_comment_list(repo_slug: str, pr_id: int, workspace: str = "") -> dict:
    try:
        return bitbucket_pr_comment_list(repo_slug=repo_slug, pr_id=pr_id, workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR comment list failed")
        return {"error": str(exc)}


class CommentIn(BaseModel):
    repo_slug: str
    pr_id: int
    content: str
    comment_id: int | None = None
    workspace: str = ""


@router.post("/pr/comment")
def bb_pr_comment_add(body: CommentIn) -> dict:
    try:
        return bitbucket_pr_comment_add(
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            content=body.content,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR comment add failed")
        return {"error": str(exc)}


@router.put("/pr/comment")
def bb_pr_comment_update(body: CommentIn) -> dict:
    try:
        return bitbucket_pr_comment_update(
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            comment_id=body.comment_id,
            content=body.content,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR comment update failed")
        return {"error": str(exc)}


@router.get("/pr/tasks")
def bb_pr_task_list(repo_slug: str, pr_id: int, workspace: str = "") -> dict:
    try:
        return bitbucket_pr_task_list(repo_slug=repo_slug, pr_id=pr_id, workspace=workspace)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR task list failed")
        return {"error": str(exc)}


class TaskIn(BaseModel):
    repo_slug: str
    pr_id: int
    content: str
    task_id: int | None = None
    state: str = ""
    workspace: str = ""


@router.post("/pr/task")
def bb_pr_task_create(body: TaskIn) -> dict:
    try:
        return bitbucket_pr_task_create(
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            content=body.content,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR task create failed")
        return {"error": str(exc)}


@router.put("/pr/task")
def bb_pr_task_update(body: TaskIn) -> dict:
    try:
        return bitbucket_pr_task_update(
            repo_slug=body.repo_slug,
            pr_id=body.pr_id,
            task_id=body.task_id,
            content=body.content,
            state=body.state,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket PR task update failed")
        return {"error": str(exc)}


@router.get("/pr/user")
def bb_user_pull_requests(selected_user: str, workspace: str = "", state: str = "OPEN") -> dict:
    try:
        return bitbucket_user_pull_requests(
            selected_user=selected_user, workspace=workspace, state=state
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket user PRs failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Pipelines (bitbucket_*) — new tools
# ---------------------------------------------------------------------------


@router.get("/pipelines")
def bb_pipeline_list(repo_slug: str, workspace: str = "", pagelen: int = 25) -> dict:
    try:
        return bitbucket_pipeline_list(repo_slug=repo_slug, workspace=workspace, pagelen=pagelen)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket pipeline list failed")
        return {"error": str(exc)}


@router.get("/pipeline")
def bb_pipeline_get(repo_slug: str, pipeline_uuid: str, workspace: str = "") -> dict:
    try:
        return bitbucket_pipeline_get(
            repo_slug=repo_slug, pipeline_uuid=pipeline_uuid, workspace=workspace
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket pipeline get failed")
        return {"error": str(exc)}


class PipelineRunIn(BaseModel):
    repo_slug: str
    ref_type: str = "branch"
    ref_name: str = ""
    selector_type: str = "custom"
    selector_pattern: str = "**"
    variables: list | None = None
    workspace: str = ""


@router.post("/pipeline/run")
def bb_pipeline_run(body: PipelineRunIn) -> dict:
    try:
        return bitbucket_pipeline_run(
            repo_slug=body.repo_slug,
            ref_type=body.ref_type,
            ref_name=body.ref_name,
            selector_type=body.selector_type,
            selector_pattern=body.selector_pattern,
            variables=body.variables,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket pipeline run failed")
        return {"error": str(exc)}


@router.get("/pipeline/steps")
def bb_pipeline_steps(repo_slug: str, pipeline_uuid: str, workspace: str = "", pagelen: int = 25) -> dict:
    try:
        return bitbucket_pipeline_steps(
            repo_slug=repo_slug, pipeline_uuid=pipeline_uuid, workspace=workspace, pagelen=pagelen
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket pipeline steps failed")
        return {"error": str(exc)}


@router.get("/pipeline/step")
def bb_pipeline_step_get(repo_slug: str, pipeline_uuid: str, step_uuid: str, workspace: str = "") -> dict:
    try:
        return bitbucket_pipeline_step_get(
            repo_slug=repo_slug,
            pipeline_uuid=pipeline_uuid,
            step_uuid=step_uuid,
            workspace=workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket pipeline step get failed")
        return {"error": str(exc)}


@router.get("/pipeline/step/log")
def bb_pipeline_step_log(repo_slug: str, pipeline_uuid: str, step_uuid: str, workspace: str = "") -> dict:
    try:
        return bitbucket_pipeline_step_log(
            repo_slug=repo_slug,
            pipeline_uuid=pipeline_uuid,
            step_uuid=step_uuid,
            workspace=workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket pipeline step log failed")
        return {"error": str(exc)}


@router.get("/pipeline/analyze/pr-failures")
def bb_analyze_pr_commit_failures(repo_slug: str, pr_id: int, workspace: str = "") -> dict:
    try:
        return bitbucket_analyze_pr_commit_failures(
            repo_slug=repo_slug, pr_id=pr_id, workspace=workspace
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket analyze PR failures failed")
        return {"error": str(exc)}


@router.get("/pipeline/analyze/step-failure")
def bb_analyze_pipeline_step_failure(
    repo_slug: str, pipeline_uuid: str, step_uuid: str, workspace: str = "", log_lines: int = 200
) -> dict:
    try:
        return bitbucket_analyze_pipeline_step_failure(
            repo_slug=repo_slug,
            pipeline_uuid=pipeline_uuid,
            step_uuid=step_uuid,
            workspace=workspace,
            log_lines=log_lines,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket analyze step failure failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Deployments & Environments (bitbucket_*) — new tools
# ---------------------------------------------------------------------------


@router.get("/deployments")
def bb_deployment_list(repo_slug: str, workspace: str = "", pagelen: int = 25) -> dict:
    try:
        return bitbucket_deployment_list(repo_slug=repo_slug, workspace=workspace, pagelen=pagelen)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket deployment list failed")
        return {"error": str(exc)}


@router.get("/deployment")
def bb_deployment_get(repo_slug: str, deployment_uuid: str, workspace: str = "") -> dict:
    try:
        return bitbucket_deployment_get(
            repo_slug=repo_slug, deployment_uuid=deployment_uuid, workspace=workspace
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket deployment get failed")
        return {"error": str(exc)}


@router.get("/environments")
def bb_environment_list(repo_slug: str, workspace: str = "", pagelen: int = 25) -> dict:
    try:
        return bitbucket_environment_list(repo_slug=repo_slug, workspace=workspace, pagelen=pagelen)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket environment list failed")
        return {"error": str(exc)}


@router.get("/environment")
def bb_environment_get(repo_slug: str, environment_uuid: str, workspace: str = "") -> dict:
    try:
        return bitbucket_environment_get(
            repo_slug=repo_slug, environment_uuid=environment_uuid, workspace=workspace
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket environment get failed")
        return {"error": str(exc)}


class EnvCreateIn(BaseModel):
    repo_slug: str
    name: str
    environment_type: str = "Production"
    workspace: str = ""


@router.post("/environment")
def bb_environment_create(body: EnvCreateIn) -> dict:
    try:
        return bitbucket_environment_create(
            repo_slug=body.repo_slug,
            name=body.name,
            environment_type=body.environment_type,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket environment create failed")
        return {"error": str(exc)}


class EnvDeleteIn(BaseModel):
    repo_slug: str
    environment_uuid: str
    workspace: str = ""
    confirmed: bool = False


@router.post("/environment/delete")
def bb_environment_delete(body: EnvDeleteIn) -> dict:
    try:
        return bitbucket_environment_delete(
            repo_slug=body.repo_slug,
            environment_uuid=body.environment_uuid,
            workspace=body.workspace,
            confirmed=body.confirmed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket environment delete failed")
        return {"error": str(exc)}


class EnvUpdateIn(BaseModel):
    repo_slug: str
    environment_uuid: str
    update: dict | None = None
    workspace: str = ""


@router.post("/environment/update")
def bb_environment_update(body: EnvUpdateIn) -> dict:
    try:
        return bitbucket_environment_update(
            repo_slug=body.repo_slug,
            environment_uuid=body.environment_uuid,
            update=body.update,
            workspace=body.workspace,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bitbucket environment update failed")
        return {"error": str(exc)}
