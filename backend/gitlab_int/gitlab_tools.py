"""
gitlab_int/gitlab_tools.py
Central GitLab tool registry — every tool the GitLab chat agent can dispatch.

Concrete implementations live in focused sibling modules (mirroring the
Bitbucket layout):

    gitlab_client.py   → python-gitlab client + shared helpers + GitLabError
    project_tools.py   → projects, commits, files, diffs, ref comparison
    mr_tools.py        → merge requests: list/get/changes/notes/create +
                         approve/unapprove/merge/close (human-gated)
    branch_tools.py    → list/get/create/delete branches
    pipeline_tools.py  → list/get pipelines + jobs
    review_agent.py    → dedicated AI code-review agent (MR / commit / range)

Each registry entry:
  name        : str  – unique snake_case tool name
  fn          : callable
  description : str  – shown to the LLM for tool selection
  params      : list[dict]  – parameter schema shown to the LLM
"""
from __future__ import annotations

from gitlab_int.branch_tools import (
    gitlab_branch_create,
    gitlab_branch_delete,
    gitlab_branch_get,
    gitlab_branch_list,
)
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
)
from gitlab_int.pipeline_tools import (
    gitlab_pipeline_get,
    gitlab_pipeline_jobs,
    gitlab_pipeline_list,
)
from gitlab_int.project_tools import (
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


def _gt(name, fn, description, params=None):
    return {"name": name, "fn": fn, "description": description, "params": params or []}


GITLAB_TOOL_REGISTRY: list[dict] = [
    # ── Projects ────────────────────────────────────────────────────────
    _gt("gitlab_project_list", gitlab_project_list,
        "List projects the token can access (most recently active first). Use "
        "this to enumerate repositories or find a project id / path.",
        [{"name": "search", "type": "str", "required": False},
         {"name": "limit", "type": "int", "required": False, "default": 50}]),
    _gt("gitlab_project_get", gitlab_project_get,
        "Get one project's details by numeric id or 'namespace/path'.",
        [{"name": "project_id", "type": "str", "required": True}]),
    _gt("gitlab_project_create", gitlab_project_create,
        "Create a new project (repository). HUMAN-GATED — requires confirmed=True. "
        "Needs project-creation rights in the target namespace; if GitLab refuses, "
        "an explicit 'you don't have permission' (403) error is returned.",
        [{"name": "name", "type": "str", "required": True},
         {"name": "namespace_id", "type": "int", "required": False},
         {"name": "path", "type": "str", "required": False},
         {"name": "visibility", "type": "str", "required": False, "default": "private"},
         {"name": "description", "type": "str", "required": False},
         {"name": "initialize_with_readme", "type": "bool", "required": False, "default": False},
         {"name": "default_branch", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_project_delete", gitlab_project_delete,
        "Delete a project (repository). HUMAN-GATED — requires confirmed=True. "
        "Needs Owner/admin; GitLab returns an explicit permission error otherwise.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_project_commits", gitlab_project_commits,
        "List the latest commits on a project (optionally for a branch/ref).",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "ref", "type": "str", "required": False},
         {"name": "limit", "type": "int", "required": False, "default": 20}]),
    _gt("gitlab_commit_get", gitlab_commit_get,
        "Get one commit with its stats (additions/deletions).",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "sha", "type": "str", "required": True}]),
    _gt("gitlab_commit_diff", gitlab_commit_diff,
        "Get the diff a commit introduced vs its parent (previous → current).",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "sha", "type": "str", "required": True}]),
    _gt("gitlab_file_get", gitlab_file_get,
        "Read the raw text of a file in a project at a ref.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "path", "type": "str", "required": True},
         {"name": "ref", "type": "str", "required": False}]),
    _gt("gitlab_compare", gitlab_compare,
        "Compare two refs (branches or SHAs) — returns the commit list and full diff.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "from_sha", "type": "str", "required": True},
         {"name": "to_sha", "type": "str", "required": True}]),

    # ── Merge requests ─────────────────────────────────────────────────
    _gt("gitlab_mr_list", gitlab_mr_list,
        "List merge requests for a project. state: opened|closed|merged|all.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "state", "type": "str", "required": False, "default": "opened"},
         {"name": "limit", "type": "int", "required": False, "default": 50}]),
    _gt("gitlab_mr_get", gitlab_mr_get,
        "Get one merge request by its project-scoped iid (with approval info when available).",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True}]),
    _gt("gitlab_mr_changes", gitlab_mr_changes,
        "Get the full diff of a merge request (all changed files) + base/head SHAs.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True}]),
    _gt("gitlab_mr_notes_list", gitlab_mr_notes_list,
        "List discussion notes (comments) on a merge request.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True},
         {"name": "limit", "type": "int", "required": False, "default": 50}]),
    _gt("gitlab_mr_note_add", gitlab_mr_note_add,
        "Post a review comment on a merge request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True},
         {"name": "body", "type": "str", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_mr_create", gitlab_mr_create,
        "Open a new merge request from source_branch into target_branch. "
        "HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "source_branch", "type": "str", "required": True},
         {"name": "target_branch", "type": "str", "required": True},
         {"name": "title", "type": "str", "required": True},
         {"name": "description", "type": "str", "required": False},
         {"name": "remove_source_branch", "type": "bool", "required": False, "default": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_mr_approve", gitlab_mr_approve,
        "Approve a merge request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_mr_unapprove", gitlab_mr_unapprove,
        "Revoke your approval on a merge request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_mr_merge", gitlab_mr_merge,
        "Merge a merge request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True},
         {"name": "merge_commit_message", "type": "str", "required": False},
         {"name": "squash", "type": "bool", "required": False, "default": False},
         {"name": "remove_source_branch", "type": "bool", "required": False, "default": False},
         {"name": "merge_when_pipeline_succeeds", "type": "bool", "required": False, "default": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_mr_close", gitlab_mr_close,
        "Close (decline) a merge request without merging. HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),

    # ── AI code review (dedicated agent) ──────────────────────────────
    _gt("gitlab_review_merge_request", gitlab_review_merge_request,
        "Run a dedicated AI code review of a merge request. Returns a structured "
        "verdict: rating (good | need_to_check | bad), risk_factor (low|medium|high), "
        "risk_score, summary, findings[], good_points[], recommendation. Call this "
        "whenever the user asks to review / check / assess an MR before approving.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "mr_iid", "type": "int", "required": True}]),
    _gt("gitlab_review_commit", gitlab_review_commit,
        "Run a dedicated AI code review of ONE commit vs its parent (previous → current). "
        "Returns the same structured verdict as gitlab_review_merge_request.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "sha", "type": "str", "required": True}]),
    _gt("gitlab_review_commit_range", gitlab_review_commit_range,
        "Run a dedicated AI code review of everything between two refs "
        "(from_sha = last known-good, to_sha = new head).",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "from_sha", "type": "str", "required": True},
         {"name": "to_sha", "type": "str", "required": True}]),

    # ── Branches ─────────────────────────────────────────────────────
    _gt("gitlab_branch_list", gitlab_branch_list,
        "List branches on a project (optionally filtered by a search substring).",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "search", "type": "str", "required": False},
         {"name": "limit", "type": "int", "required": False, "default": 100}]),
    _gt("gitlab_branch_get", gitlab_branch_get,
        "Get one branch on a project.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "branch", "type": "str", "required": True}]),
    _gt("gitlab_branch_create", gitlab_branch_create,
        "Create a branch from a ref (defaults to the project default branch). "
        "HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "branch", "type": "str", "required": True},
         {"name": "ref", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _gt("gitlab_branch_delete", gitlab_branch_delete,
        "Delete a branch. HUMAN-GATED — requires confirmed=True.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "branch", "type": "str", "required": True},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),

    # ── Pipelines ───────────────────────────────────────────────────
    _gt("gitlab_pipeline_list", gitlab_pipeline_list,
        "List recent pipelines for a project (optionally filtered by ref).",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "ref", "type": "str", "required": False},
         {"name": "limit", "type": "int", "required": False, "default": 20}]),
    _gt("gitlab_pipeline_get", gitlab_pipeline_get,
        "Get one pipeline with its status and duration.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "pipeline_id", "type": "int", "required": True}]),
    _gt("gitlab_pipeline_jobs", gitlab_pipeline_jobs,
        "List the jobs of a pipeline with per-stage status and failure reason.",
        [{"name": "project_id", "type": "str", "required": True},
         {"name": "pipeline_id", "type": "int", "required": True},
         {"name": "limit", "type": "int", "required": False, "default": 50}]),
]

# Lookup by name
GITLAB_TOOL_MAP: dict[str, dict] = {t["name"]: t for t in GITLAB_TOOL_REGISTRY}
