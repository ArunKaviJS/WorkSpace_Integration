"""
tools/task_tools.py
ClickUp task tools – fetch, create, update, filter by status.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from config.settings import CLICKUP_BASE_URL, CLICKUP_HEADERS

logger = logging.getLogger(__name__)

COMPLETED_STATUSES = {"complete", "closed", "done", "finished"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(endpoint: str, params: dict | None = None) -> Any:
    url = f"{CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.get(url, headers=CLICKUP_HEADERS, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(endpoint: str, payload: dict) -> Any:
    url = f"{CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.post(url, headers=CLICKUP_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _put(endpoint: str, payload: dict) -> Any:
    url = f"{CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.put(url, headers=CLICKUP_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _delete(endpoint: str) -> Any:
    url = f"{CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.delete(url, headers=CLICKUP_HEADERS, timeout=30)
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


def _fmt_task(t: dict) -> dict:
    """Normalise a raw ClickUp task object."""
    assignees = [a.get("username") for a in t.get("assignees", [])]
    due_ts = t.get("due_date")
    due_sec = int(due_ts) / 1000 if due_ts else None
    now = time.time()

    status_name = (t.get("status") or {}).get("status", "").lower()
    is_complete = status_name in COMPLETED_STATUSES
    overdue = (not is_complete) and due_sec is not None and due_sec < now
    due_soon = (
        not is_complete
        and due_sec is not None
        and 0 < (due_sec - now) <= 300  # within 5 minutes
    )

    return {
        "id": t["id"],
        "name": t["name"],
        "status": status_name,
        "is_complete": is_complete,
        "overdue": overdue,
        "due_soon_5min": due_soon,
        "due_date_epoch": due_sec,
        "priority": (t.get("priority") or {}).get("priority"),
        "assignees": assignees,
        "url": t.get("url"),
        "description": t.get("description", ""),
        "tags": [tg["name"] for tg in t.get("tags", [])],
    }


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def get_tasks(list_id: str, include_closed: bool = True) -> list[dict]:
    """
    TOOL: get_tasks
    Fetch all tasks in a ClickUp list and classify each one.

    Parameters
    ----------
    list_id       : str
    include_closed: bool – include completed/closed tasks (default True)
    """
    params = {
        "include_closed": str(include_closed).lower(),
        "subtasks": "true",
        "page": 0,
    }
    all_tasks: list[dict] = []
    while True:
        data = _get(f"/list/{list_id}/task", params)
        batch = data.get("tasks", [])
        all_tasks.extend(batch)
        if len(batch) < 100:  # ClickUp returns max 100 per page
            break
        params["page"] += 1  # type: ignore[operator]

    return [_fmt_task(t) for t in all_tasks]


def get_task(task_id: str) -> dict:
    """
    TOOL: get_task
    Fetch a single task by its ID.

    Parameters
    ----------
    task_id : str
    """
    data = _get(f"/task/{task_id}")
    return _fmt_task(data)


def get_team_tasks(
    team_id: str,
    assignee_ids: list[int] | None = None,
) -> list[dict]:
    """
    TOOL: get_team_tasks
    Fetch tasks across the whole workspace, optionally filtered by assignees.

    Parameters
    ----------
    team_id      : str
    assignee_ids : list[int] | None – ClickUp user IDs to filter by
    """
    params: dict[str, Any] = {"include_closed": "true", "subtasks": "true", "page": 0}
    if assignee_ids:
        params["assignees[]"] = assignee_ids

    all_tasks: list[dict] = []
    while True:
        data = _get(f"/team/{team_id}/task", params)
        batch = data.get("tasks", [])
        all_tasks.extend(batch)
        if len(batch) < 100:
            break
        params["page"] += 1  # type: ignore[operator]

    return [_fmt_task(t) for t in all_tasks]


def classify_tasks(tasks: list[dict]) -> dict:
    """
    TOOL: classify_tasks
    Group a list of (already-formatted) tasks into completed / pending / overdue / due_soon.

    Parameters
    ----------
    tasks : list of dicts returned by get_tasks / get_team_tasks
    """
    completed, pending, overdue, due_soon = [], [], [], []
    for t in tasks:
        if t["is_complete"]:
            completed.append(t)
        elif t["overdue"]:
            overdue.append(t)
        elif t["due_soon_5min"]:
            due_soon.append(t)
        else:
            pending.append(t)
    return {
        "completed": completed,
        "pending": pending,
        "overdue": overdue,
        "due_soon_5min": due_soon,
        "total": len(tasks),
    }


def create_task(
    list_id: str,
    name: str,
    description: str = "",
    assignee_ids: list[int] | None = None,
    status: str | None = None,
    priority: int | None = None,
    due_date_epoch_ms: int | None = None,
    tags: list[str] | None = None,
    notify_all: bool = False,
) -> dict:
    """
    TOOL: create_task
    Create a new task in a ClickUp list.

    Parameters
    ----------
    list_id            : str   – target list
    name               : str   – task title (required)
    description        : str   – markdown description
    assignee_ids       : list[int] – ClickUp user IDs
    status             : str   – e.g. "open", "in progress"
    priority           : int   – 1=Urgent 2=High 3=Normal 4=Low
    due_date_epoch_ms  : int   – Unix timestamp in milliseconds
    tags               : list[str]
    notify_all         : bool  – notify all assignees
    """
    payload: dict[str, Any] = {"name": name, "notify_all": notify_all}
    if description:
        payload["description"] = description
    if assignee_ids:
        payload["assignees"] = assignee_ids
    if status:
        payload["status"] = status
    if priority is not None:
        payload["priority"] = priority
    if due_date_epoch_ms is not None:
        payload["due_date"] = due_date_epoch_ms
        payload["due_date_time"] = True
    if tags:
        payload["tags"] = tags

    data = _post(f"/list/{list_id}/task", payload)
    return _fmt_task(data)


def update_task_status(task_id: str, new_status: str) -> dict:
    """
    TOOL: update_task_status
    Update the status of an existing task.

    Parameters
    ----------
    task_id    : str
    new_status : str – e.g. "in progress", "complete"
    """
    data = _put(f"/task/{task_id}", {"status": new_status})
    return _fmt_task(data)


def update_task(task_id: str, fields: dict) -> dict:
    """
    TOOL: update_task
    Generic task update – pass any updatable fields.

    Parameters
    ----------
    task_id : str
    fields  : dict – e.g. {"name": "...", "priority": 2, "due_date": 1234567890000}
    """
    data = _put(f"/task/{task_id}", fields)
    return _fmt_task(data)


def delete_task(task_id: str) -> dict:
    """
    TOOL: delete_task
    Permanently delete a task or subtask by its ID.
    (The agent should confirm with the user before calling this.)

    Parameters
    ----------
    task_id : str
    """
    _delete(f"/task/{task_id}")
    return {"deleted": True, "task_id": task_id}


def get_list_custom_fields(list_id: str) -> list[dict]:
    """
    TOOL: get_list_custom_fields
    Get all custom fields available on tasks in a list
    (needed to discover field IDs before setting values).

    Parameters
    ----------
    list_id : str
    """
    data = _get(f"/list/{list_id}/field")
    return [
        {
            "id": f["id"],
            "name": f.get("name"),
            "type": f.get("type"),
            "options": [
                {"id": o["id"], "name": o["name"]}
                for o in (f.get("type_config") or {}).get("options", [])
            ],
        }
        for f in data.get("fields", [])
    ]


def set_custom_field(task_id: str, field_id: str, value: Any) -> dict:
    """
    TOOL: set_custom_field
    Set a custom field value on a task.
    For dropdown fields pass the option ID; for text/number pass the raw value.

    Parameters
    ----------
    task_id  : str
    field_id : str – discover via get_list_custom_fields
    value    : str | int | float | list[str]
    """
    return _post(f"/task/{task_id}/field/{field_id}", {"value": value})
