"""
tools/__init__.py
Central tool registry — every tool the orchestrator can dispatch.

Each entry:
  name        : str  – unique snake_case tool name
  fn          : callable
  description : str  – shown to the LLM for tool selection
  params      : list[dict]  – parameter schema shown to LLM
"""
from __future__ import annotations

from tools.workspace_tools import (
    get_authorized_user,
    get_workspaces,
    get_spaces,
    get_folders,
    get_lists,
    get_folderless_lists,
    get_workspace_members,
)
from tools.task_tools import (
    get_tasks,
    get_task,
    get_team_tasks,
    classify_tasks,
    create_task,
    update_task_status,
    update_task,
)
from tools.comment_tools import get_task_comments, post_task_comment
from tools.dashboard_tools import build_dashboard, render_dashboard_text


TOOL_REGISTRY: list[dict] = [
    # ── Workspace ──────────────────────────────────────────────────────
    {
        "name": "get_authorized_user",
        "fn": get_authorized_user,
        "description": "Get info about the authenticated ClickUp user.",
        "params": [],
    },
    {
        "name": "get_workspaces",
        "fn": get_workspaces,
        "description": "List all ClickUp workspaces the user belongs to.",
        "params": [],
    },
    {
        "name": "get_spaces",
        "fn": get_spaces,
        "description": "Get all spaces in a workspace.",
        "params": [{"name": "team_id", "type": "str", "required": True}],
    },
    {
        "name": "get_folders",
        "fn": get_folders,
        "description": "Get all folders in a space.",
        "params": [{"name": "space_id", "type": "str", "required": True}],
    },
    {
        "name": "get_lists",
        "fn": get_lists,
        "description": "Get all lists in a folder.",
        "params": [{"name": "folder_id", "type": "str", "required": True}],
    },
    {
        "name": "get_folderless_lists",
        "fn": get_folderless_lists,
        "description": "Get lists that live directly under a space (not in any folder).",
        "params": [{"name": "space_id", "type": "str", "required": True}],
    },
    {
        "name": "get_workspace_members",
        "fn": get_workspace_members,
        "description": "Get all members of a workspace — useful before assigning tasks.",
        "params": [{"name": "team_id", "type": "str", "required": True}],
    },
    # ── Tasks ──────────────────────────────────────────────────────────
    {
        "name": "get_tasks",
        "fn": get_tasks,
        "description": "Fetch and classify all tasks in a ClickUp list.",
        "params": [
            {"name": "list_id", "type": "str", "required": True},
            {"name": "include_closed", "type": "bool", "required": False, "default": True},
        ],
    },
    {
        "name": "get_task",
        "fn": get_task,
        "description": "Fetch a single ClickUp task by its ID.",
        "params": [{"name": "task_id", "type": "str", "required": True}],
    },
    {
        "name": "get_team_tasks",
        "fn": get_team_tasks,
        "description": "Fetch tasks across an entire workspace, optionally filtered by assignees.",
        "params": [
            {"name": "team_id", "type": "str", "required": True},
            {"name": "assignee_ids", "type": "list[int]", "required": False},
        ],
    },
    {
        "name": "classify_tasks",
        "fn": classify_tasks,
        "description": "Classify a list of tasks into completed / pending / overdue / due_soon buckets.",
        "params": [{"name": "tasks", "type": "list[dict]", "required": True}],
    },
    {
        "name": "create_task",
        "fn": create_task,
        "description": (
            "Create a new task in a ClickUp list. "
            "Requires list_id and name. Optionally: description, assignee_ids, status, "
            "priority (1=Urgent 2=High 3=Normal 4=Low), due_date_epoch_ms, tags."
        ),
        "params": [
            {"name": "list_id", "type": "str", "required": True},
            {"name": "name", "type": "str", "required": True},
            {"name": "description", "type": "str", "required": False},
            {"name": "assignee_ids", "type": "list[int]", "required": False},
            {"name": "status", "type": "str", "required": False},
            {"name": "priority", "type": "int", "required": False},
            {"name": "due_date_epoch_ms", "type": "int", "required": False},
            {"name": "tags", "type": "list[str]", "required": False},
            {"name": "notify_all", "type": "bool", "required": False},
        ],
    },
    {
        "name": "update_task_status",
        "fn": update_task_status,
        "description": "Update the status of a ClickUp task.",
        "params": [
            {"name": "task_id", "type": "str", "required": True},
            {"name": "new_status", "type": "str", "required": True},
        ],
    },
    {
        "name": "update_task",
        "fn": update_task,
        "description": "Generic task update — pass a dict of fields to change.",
        "params": [
            {"name": "task_id", "type": "str", "required": True},
            {"name": "fields", "type": "dict", "required": True},
        ],
    },
    # ── Comments ───────────────────────────────────────────────────────
    {
        "name": "get_task_comments",
        "fn": get_task_comments,
        "description": "Get comments on a ClickUp task.",
        "params": [{"name": "task_id", "type": "str", "required": True}],
    },
    {
        "name": "post_task_comment",
        "fn": post_task_comment,
        "description": "Post a comment on a ClickUp task.",
        "params": [
            {"name": "task_id", "type": "str", "required": True},
            {"name": "comment_text", "type": "str", "required": True},
            {"name": "notify_all", "type": "bool", "required": False},
        ],
    },
    # ── Dashboard ──────────────────────────────────────────────────────
    {
        "name": "build_dashboard",
        "fn": build_dashboard,
        "description": "Build a structured dashboard dict from classified task data.",
        "params": [
            {"name": "classified", "type": "dict", "required": True},
            {"name": "member_map", "type": "dict", "required": False},
        ],
    },
    {
        "name": "render_dashboard_text",
        "fn": render_dashboard_text,
        "description": "Render a dashboard dict as a human-readable text report.",
        "params": [{"name": "dashboard", "type": "dict", "required": True}],
    },
]

# Lookup by name
TOOL_MAP: dict[str, dict] = {t["name"]: t for t in TOOL_REGISTRY}
