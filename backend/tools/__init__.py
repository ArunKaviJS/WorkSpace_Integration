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
    delete_task,
    get_list_custom_fields,
    set_custom_field,
)
from tools.comment_tools import get_task_comments, post_task_comment
from tools.dashboard_tools import build_dashboard, render_dashboard_text

# ── New modules (ClickUp AI-assistant parity) ──────────────────────────────
from tools.search_tools import search_workspace, search_tasks_by_type, search_tasks_by_tag
from tools.bulk_tools import create_bulk_tasks, update_bulk_tasks
from tools.tag_tools import add_tag_to_task, remove_tag_from_task
from tools.relation_tools import add_task_link, remove_task_link, add_dependency, remove_dependency
from tools.list_tools import (
    move_task_to_list,
    add_task_to_list,
    create_folder,
    update_folder,
    get_folder_details,
    create_list,
    update_list,
    get_list_details,
    get_workspace_hierarchy,
)
from tools.attachment_tools import attach_file_to_task
from tools.time_tracking_tools import (
    get_task_time_entries,
    get_time_entries_summary,
    start_time_tracking,
    stop_time_tracking,
    add_time_entry,
    get_current_time_entry,
)
from tools.status_time_tools import get_task_time_in_status, get_list_time_in_status
from tools.member_tools import find_member_by_name, resolve_assignees
from tools.chat_tools import get_chat_channels, send_chat_message
from tools.docs_tools import (
    create_document,
    list_document_pages,
    get_document_pages,
    create_document_page,
    update_document_page,
)


def _t(name: str, fn, description: str, params: list[dict] | None = None) -> dict:
    return {"name": name, "fn": fn, "description": description, "params": params or []}


TOOL_REGISTRY: list[dict] = [
    # ── Workspace / hierarchy ────────────────────────────────────────────
    _t("get_authorized_user", get_authorized_user,
       "Get info about the authenticated ClickUp user."),
    _t("get_workspaces", get_workspaces,
       "List all ClickUp workspaces the user belongs to."),
    _t("get_spaces", get_spaces,
       "Get all spaces in a workspace.",
       [{"name": "team_id", "type": "str", "required": True}]),
    _t("get_folders", get_folders,
       "Get all folders in a space.",
       [{"name": "space_id", "type": "str", "required": True}]),
    _t("get_lists", get_lists,
       "Get all lists in a folder.",
       [{"name": "folder_id", "type": "str", "required": True}]),
    _t("get_folderless_lists", get_folderless_lists,
       "Get lists that live directly under a space (not in any folder).",
       [{"name": "space_id", "type": "str", "required": True}]),
    _t("get_workspace_hierarchy", get_workspace_hierarchy,
       "Retrieve the FULL workspace structure: every Space with its Folders and Lists. "
       "Use this to answer questions about the whole workspace layout at once.",
       [{"name": "team_id", "type": "str", "required": True}]),

    # ── Search ───────────────────────────────────────────────────────────
    _t("search_workspace", search_workspace,
       "Search across the entire workspace: tasks by name, plus spaces, folders and lists. "
       'Example: find all tasks related to the "Q4 Marketing Launch".',
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "query", "type": "str", "required": True}]),
    _t("search_tasks_by_type", search_tasks_by_type,
       'Retrieve workspace tasks filtered by type. task_type is "task" or "subtask". '
       'Example: show me all subtasks.',
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "task_type", "type": "str", "required": False, "default": "task"}]),
    _t("search_tasks_by_tag", search_tasks_by_tag,
       'Retrieve workspace tasks filtered by tags. Example: tasks with the "UX-quality" tag.',
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "tags", "type": "list[str]", "required": True}]),

    # ── Task management ──────────────────────────────────────────────────
    _t("get_tasks", get_tasks,
       "Fetch and classify all tasks in a ClickUp list.",
       [{"name": "list_id", "type": "str", "required": True},
        {"name": "include_closed", "type": "bool", "required": False, "default": True}]),
    _t("get_task", get_task,
       "Fetch full details of a single task by its ID.",
       [{"name": "task_id", "type": "str", "required": True}]),
    _t("get_team_tasks", get_team_tasks,
       "Fetch tasks across an entire workspace, optionally filtered by assignees.",
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "assignee_ids", "type": "list[int]", "required": False}]),
    _t("classify_tasks", classify_tasks,
       "Classify a list of tasks into completed / pending / overdue / due_soon buckets.",
       [{"name": "tasks", "type": "list[dict]", "required": True}]),
    _t("create_task", create_task,
       "Create a new task in a ClickUp list. Requires list_id and name. Optionally: "
       "description, assignee_ids, status, priority (1=Urgent 2=High 3=Normal 4=Low), "
       "due_date_epoch_ms, tags.",
       [{"name": "list_id", "type": "str", "required": True},
        {"name": "name", "type": "str", "required": True},
        {"name": "description", "type": "str", "required": False},
        {"name": "assignee_ids", "type": "list[int]", "required": False},
        {"name": "status", "type": "str", "required": False},
        {"name": "priority", "type": "int", "required": False},
        {"name": "due_date_epoch_ms", "type": "int", "required": False},
        {"name": "tags", "type": "list[str]", "required": False},
        {"name": "notify_all", "type": "bool", "required": False}]),
    _t("update_task_status", update_task_status,
       "Update the status of a ClickUp task.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "new_status", "type": "str", "required": True}]),
    _t("update_task", update_task,
       "Generic task update — change name, description, assignees, due date etc. "
       "via a fields dict.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "fields", "type": "dict", "required": True}]),
    _t("delete_task", delete_task,
       "Permanently DELETE a task or subtask. Confirm with the user before calling this.",
       [{"name": "task_id", "type": "str", "required": True}]),
    _t("set_custom_field", set_custom_field,
       "Set a custom field on a task. Discover field/option IDs first via "
       "get_list_custom_fields. Example: set release number to 4.07.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "field_id", "type": "str", "required": True},
        {"name": "value", "type": "any", "required": True}]),
    _t("get_list_custom_fields", get_list_custom_fields,
       "List custom fields (and dropdown option IDs) available on a list's tasks — "
       "call before set_custom_field.",
       [{"name": "list_id", "type": "str", "required": True}]),

    # ── Bulk ─────────────────────────────────────────────────────────────
    _t("create_bulk_tasks", create_bulk_tasks,
       "Create multiple tasks in one list with shared defaults. "
       'Example: add "Send welcome email", "Schedule orientation" to Onboarding.',
       [{"name": "list_id", "type": "str", "required": True},
        {"name": "names", "type": "list[str]", "required": True},
        {"name": "assignee_ids", "type": "list[int]", "required": False},
        {"name": "priority", "type": "int", "required": False},
        {"name": "due_date_epoch_ms", "type": "int", "required": False}]),
    _t("update_bulk_tasks", update_bulk_tasks,
       "Apply the same field changes to many tasks at once. "
       'Example: set status "In Review" on a group of task IDs.',
       [{"name": "task_ids", "type": "list[str]", "required": True},
        {"name": "fields", "type": "dict", "required": True}]),

    # ── Attachments ──────────────────────────────────────────────────────
    _t("attach_file_to_task", attach_file_to_task,
       "Upload and attach a local file (document/image/ZIP) to a task via its absolute path.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "file_path", "type": "str", "required": True}]),

    # ── Comments ─────────────────────────────────────────────────────────
    _t("get_task_comments", get_task_comments,
       "Get comments on a ClickUp task.",
       [{"name": "task_id", "type": "str", "required": True}]),
    _t("post_task_comment", post_task_comment,
       "Post a comment on a task; supports @mentions in text.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "comment_text", "type": "str", "required": True},
        {"name": "notify_all", "type": "bool", "required": False}]),

    # ── Tags ─────────────────────────────────────────────────────────────
    _t("add_tag_to_task", add_tag_to_task,
       'Apply an existing tag to a task. Example: add "Urgent" to a bug task.',
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "tag_name", "type": "str", "required": True}]),
    _t("remove_tag_from_task", remove_tag_from_task,
       'Remove a tag from a task. Example: remove "Backend" from a task.',
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "tag_name", "type": "str", "required": True}]),

    # ── Relationships ────────────────────────────────────────────────────
    _t("add_task_link", add_task_link,
       "Relate two tasks by linking them.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "linked_task_id", "type": "str", "required": True}]),
    _t("remove_task_link", remove_task_link,
       "Remove the link between two tasks.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "linked_task_id", "type": "str", "required": True}]),
    _t("add_dependency", add_dependency,
       "Create a dependency between tasks. depends_on = this task is blocked by that task. "
       'Pass exactly one of depends_on / dependency_of.',
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "depends_on", "type": "str", "required": False},
        {"name": "dependency_of", "type": "str", "required": False}]),
    _t("remove_dependency", remove_dependency,
       "Remove a dependency between two tasks. Pass exactly one of depends_on / dependency_of.",
       [{"name": "task_id", "type": "str", "required": True},
        {"name": "depends_on", "type": "str", "required": False},
        {"name": "dependency_of", "type": "str", "required": False}]),

    # ── Move / add tasks between lists ───────────────────────────────────
    _t("move_task_to_list", move_task_to_list,
       "Move a task to a new home list (removes it from the old one).",
       [{"name": "list_id", "type": "str", "required": True},
        {"name": "task_id", "type": "str", "required": True}]),
    _t("add_task_to_list", add_task_to_list,
       "Add a task to another list while keeping it in its current list too.",
       [{"name": "list_id", "type": "str", "required": True},
        {"name": "task_id", "type": "str", "required": True}]),

    # ── List & folder management ─────────────────────────────────────────
    _t("get_folder_details", get_folder_details,
       "Get a single folder including all lists it contains.",
       [{"name": "folder_id", "type": "str", "required": True}]),
    _t("create_folder", create_folder,
       'Create a new folder inside a space. Example: "Q1 Projects" in Operations.',
       [{"name": "space_id", "type": "str", "required": True},
        {"name": "name", "type": "str", "required": True}]),
    _t("update_folder", update_folder,
       "Rename an existing folder.",
       [{"name": "folder_id", "type": "str", "required": True},
        {"name": "name", "type": "str", "required": True}]),
    _t("create_list", create_list,
       "Create a new list inside a folder OR directly under a space (pass exactly one parent).",
       [{"name": "name", "type": "str", "required": True},
        {"name": "space_id", "type": "str", "required": False},
        {"name": "folder_id", "type": "str", "required": False}]),
    _t("get_list_details", get_list_details,
       "Get settings and custom statuses of a single list.",
       [{"name": "list_id", "type": "str", "required": True}]),
    _t("update_list", update_list,
       "Modify list settings — e.g. rename it or change color/content.",
       [{"name": "list_id", "type": "str", "required": True},
        {"name": "fields", "type": "dict", "required": True}]),

    # ── Time tracking ────────────────────────────────────────────────────
    _t("get_task_time_entries", get_task_time_entries,
       "Retrieve all time log entries for a specific task.",
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "task_id", "type": "str", "required": True}]),
    _t("get_time_entries_summary", get_time_entries_summary,
       "Total tracked time across multiple tasks (pass all IDs from a list/folder/space).",
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "task_ids", "type": "list[str]", "required": True}]),
    _t("start_time_tracking", start_time_tracking,
       "Start a timer on a task for the current user.",
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "task_id", "type": "str", "required": True}]),
    _t("stop_time_tracking", stop_time_tracking,
       "Stop the currently running timer for the current user.",
       [{"name": "team_id", "type": "str", "required": True}]),
    _t("add_time_entry", add_time_entry,
       "Manually log a block of time to a task (start epoch ms + duration ms).",
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "task_id", "type": "str", "required": True},
        {"name": "start_epoch_ms", "type": "int", "required": True},
        {"name": "duration_ms", "type": "int", "required": True}]),
    _t("get_current_time_entry", get_current_time_entry,
       "Check if the current user has a timer running and return its details.",
       [{"name": "team_id", "type": "str", "required": True}]),

    # ── Time in status reporting ─────────────────────────────────────────
    _t("get_task_time_in_status", get_task_time_in_status,
       "How long has a task spent in each status?",
       [{"name": "task_id", "type": "str", "required": True}]),
    _t("get_list_time_in_status", get_list_time_in_status,
       "Time-in-status metrics for tasks in a list — e.g. average time in QA review.",
       [{"name": "list_id", "type": "str", "required": True}]),

    # ── Members & assignees ──────────────────────────────────────────────
    _t("get_workspace_members", get_workspace_members,
       "Get all members/guests of a workspace.",
       [{"name": "team_id", "type": "str", "required": True}]),
    _t("find_member_by_name", find_member_by_name,
       "Search a workspace member by name or email. Example: David Smith's user ID.",
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "query", "type": "str", "required": True}]),
    _t("resolve_assignees", resolve_assignees,
       "Resolve names/emails into ClickUp user IDs before assigning tasks. "
       'Call this when a user says "assign to Mark and Sarah".',
       [{"name": "team_id", "type": "str", "required": True},
        {"name": "names", "type": "list[str]", "required": True}]),

    # ── Chat (v3 API — may require OAuth token) ──────────────────────────
    _t("get_chat_channels", get_chat_channels,
       "List all Chat channels (views) in the workspace.",
       [{"name": "workspace_id", "type": "str", "required": True}]),
    _t("send_chat_message", send_chat_message,
       'Send a message to a Chat channel. Example: "Team lunch at 1 PM today."',
       [{"name": "workspace_id", "type": "str", "required": True},
        {"name": "channel_id", "type": "str", "required": True},
        {"name": "message_text", "type": "str", "required": True}]),

    # ── Docs (v3 API — may require OAuth token) ──────────────────────────
    _t("create_document", create_document,
       "Create a new Doc, optionally inside a Space.",
       [{"name": "workspace_id", "type": "str", "required": True},
        {"name": "name", "type": "str", "required": True},
        {"name": "space_id", "type": "str", "required": False}]),
    _t("list_document_pages", list_document_pages,
       "Get the table of contents (all pages) of a Doc.",
       [{"name": "workspace_id", "type": "str", "required": True},
        {"name": "doc_id", "type": "str", "required": True}]),
    _t("get_document_pages", get_document_pages,
       "Read page content from a Doc. Omit page_ids to read all top-level pages.",
       [{"name": "workspace_id", "type": "str", "required": True},
        {"name": "doc_id", "type": "str", "required": True},
        {"name": "page_ids", "type": "list[str]", "required": False}]),
    _t("create_document_page", create_document_page,
       "Add a new page to an existing Doc.",
       [{"name": "doc_id", "type": "str", "required": True},
        {"name": "name", "type": "str", "required": True},
        {"name": "content_markdown", "type": "str", "required": False}]),
    _t("update_document_page", update_document_page,
       "Edit the content of an existing Doc page.",
       [{"name": "page_id", "type": "str", "required": True},
        {"name": "doc_id", "type": "str", "required": True},
        {"name": "content_markdown", "type": "str", "required": True}]),

    # ── Dashboard ────────────────────────────────────────────────────────
    _t("build_dashboard", build_dashboard,
       "Build a structured dashboard dict from classified task data.",
       [{"name": "classified", "type": "dict", "required": True},
        {"name": "member_map", "type": "dict", "required": False}]),
    _t("render_dashboard_text", render_dashboard_text,
       "Render a dashboard dict as a human-readable text report.",
       [{"name": "dashboard", "type": "dict", "required": True}]),
]

# Lookup by name
TOOL_MAP: dict[str, dict] = {t["name"]: t for t in TOOL_REGISTRY}
