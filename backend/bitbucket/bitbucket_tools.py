"""
bitbucket/bitbucket_tools.py
Central Bitbucket tool registry — every tool the Bitbucket agent can dispatch.

The concrete tool implementations now live in focused sibling modules, each
named after its domain (mirroring the ClickUp tools/ layout):

    bitbucket_http.py    → shared HTTP helpers + response normalizers
    repos_tools.py       → repository CRUD, enumeration, source writes,
                           raw-file reads, permissions, commits
    pr_tools.py          → PR diffs, comments, approve/decline/merge, pending
    branch_tools.py      → create branch, set branch permissions
    webhook_tools.py     → list / add / remove webhooks
    property_tools.py    → application-property get / update / delete
    workspace_tools.py   → list workspace members (role changes unsupported)

Each registry entry:
  name        : str  – unique snake_case tool name
  fn          : callable
  description : str  – shown to the LLM for tool selection
  params      : list[dict]  – parameter schema shown to LLM

Adding a new tool = add its function in the right module + one registry entry.
Nothing else changes.
"""
from __future__ import annotations

from bitbucket.repos_tools import (
    create_repo,
    delete_repo,
    get_latest_commits,
    get_raw_file,
    get_repository_permissions,
    invite_collaborator,
    list_repos,
    pull_repo_info,
    push_to_repo,
)
from bitbucket.pr_tools import (
    approve_pr,
    decline_pr,
    get_pending_prs,
    get_pr_diff,
    merge_pr,
    post_pr_comment,
)
from bitbucket.branch_tools import create_branch, set_branch_permission
from bitbucket.webhook_tools import add_webhook, list_webhooks, remove_webhook
from bitbucket.workspace_tools import list_workspace_members, update_workspace_member_role
from bitbucket.property_tools import (
    delete_application_properties,
    get_application_properties,
    update_application_properties,
)


def _bt(name, fn, description, params=None):
    return {"name": name, "fn": fn, "description": description, "params": params or []}


BITBUCKET_TOOL_REGISTRY: list[dict] = [
    # ── Repos ────────────────────────────────────────────────────────────
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
    _bt("list_repos", list_repos,
        "List ALL repositories in a Bitbucket workspace (name, slug, language, "
        "visibility, description, last-updated). Use this to enumerate repos or "
        "answer workspace repository questions.",
        [{"name": "workspace", "type": "str", "required": False}]),
    _bt("list_workspace_members", list_workspace_members,
        "List ALL members (users) of a Bitbucket workspace with their workspace "
        "role (owner/admin/member). Use this to answer questions about who is in "
        "the workspace or to find a user.",
        [{"name": "workspace", "type": "str", "required": False}]),
    _bt("update_workspace_member_role", update_workspace_member_role,
        "Changing a workspace member's role (owner/admin/member) is NOT supported "
        "by the Bitbucket Cloud REST API — it returns a clear 'not supported' error. "
        "Use this only to explain that the capability is unavailable; direct the user "
        "to the Atlassian administration interface instead.",
        [{"name": "selected_user_id", "type": "str", "required": True},
         {"name": "role", "type": "str", "required": True},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("pull_repo_info", pull_repo_info,
        "Pull / read repository metadata and file listing.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("push_to_repo", push_to_repo,
        "Push changes to a repository via the source-content API (update/create a file).",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "file_path", "type": "str", "required": True},
         {"name": "content", "type": "str", "required": True},
         {"name": "message", "type": "str", "required": True},
         {"name": "branch", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("get_raw_file", get_raw_file,
        "Access a raw file (the raw-file / download section permission). Read unrendered file content at a path.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "path", "type": "str", "required": True},
         {"name": "revision", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("get_repository_permissions", get_repository_permissions,
        "Get permissions for a specific user (or all users) on a repository.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "user_email_or_uuid", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("invite_collaborator", invite_collaborator,
        "Invite a user to a repository with a specified role.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "email_or_uuid", "type": "str", "required": True},
         {"name": "role", "type": "str", "required": False, "default": "write"},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("get_latest_commits", get_latest_commits,
        "Fetch the latest 10 commits for a repo (who, when, message).",
        [{"name": "repo_slug", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "limit", "type": "int", "required": False, "default": 10}]),

    # ── Pull requests ────────────────────────────────────────────────────
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
    _bt("merge_pr", merge_pr,
        "Merge / fulfill a pull request. HUMAN-GATED — requires confirmed=True.",
        [{"name": "workspace", "type": "str", "required": False},
         {"name": "repo_slug", "type": "str", "required": True},
         {"name": "pr_id", "type": "int", "required": True},
         {"name": "merge_strategy", "type": "str", "required": False, "default": "merge_commit"},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),
    _bt("get_pending_prs", get_pending_prs,
        "Fetch all open pull requests waiting for review (repo, author, title).",
        [{"name": "repo_slug", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),

    # ── Branches ─────────────────────────────────────────────────────────
    _bt("create_branch", create_branch,
        "Create a branch from a given commit SHA.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "branch_name", "type": "str", "required": True},
         {"name": "from_commit", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False}]),
    _bt("set_branch_permission", set_branch_permission,
        "Set branch restrictions / permissions on a repository. HUMAN-GATED.",
        [{"name": "repo_slug", "type": "str", "required": True},
         {"name": "branch_pattern", "type": "str", "required": True},
         {"name": "kind", "type": "str", "required": True},
         {"name": "value", "type": "str", "required": False},
         {"name": "workspace", "type": "str", "required": False},
         {"name": "confirmed", "type": "bool", "required": False, "default": False}]),

    # ── Webhooks ─────────────────────────────────────────────────────────
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

    # ── Application properties ───────────────────────────────────────────
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
