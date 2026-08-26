"""
tools/search_tools.py
Search across the workspace: tasks by name/type/tag, plus lists, folders and docs.
"""
from __future__ import annotations

from tools.http import get
from tools.task_tools import _fmt_task


def search_workspace(team_id: str, query: str) -> dict:
    """
    TOOL: search_workspace
    Search for items matching a query across the entire ClickUp Workspace:
    tasks (by name), spaces, folders, lists.

    Parameters
    ----------
    team_id : str – workspace ID
    query   : str – free-text search term
    """
    q = query.lower()

    # Tasks — fetch workspace tasks and filter client-side
    params: dict = {"include_closed": "true", "subtasks": "true", "page": 0}
    matched_tasks: list[dict] = []
    while True:
        data = get(f"/team/{team_id}/task", params)
        batch = data.get("tasks", [])
        for t in batch:
            if q in t.get("name", "").lower():
                matched_tasks.append(_fmt_task(t))
        if len(batch) < 100 or len(matched_tasks) >= 50:
            break
        params["page"] += 1

    # Spaces / Folders / Lists — name matches via hierarchy walk
    spaces_out, folders_out, lists_out = [], [], []
    for space in get(f"/team/{team_id}/space", {"archived": "false"}).get("spaces", []):
        if q in space["name"].lower():
            spaces_out.append({"id": space["id"], "name": space["name"]})
        for folder in get(f"/space/{space['id']}/folder", {"archived": "false"}).get("folders", []):
            if q in folder["name"].lower():
                folders_out.append({"id": folder["id"], "name": folder["name"]})
        for src in (
            get(f"/space/{space['id']}/list", {"archived": "false"}).get("lists", []),
            get(f"/folder/{folder['id']}/list", {"archived": "false"}).get("lists", []) if folder else [],
        ):
            for lst in src:
                if q in lst["name"].lower():
                    lists_out.append({"id": lst["id"], "name": lst["name"]})

    return {
        "query": query,
        "tasks": matched_tasks,
        "spaces": spaces_out,
        "folders": folders_out,
        "lists": lists_out,
    }


def search_tasks_by_type(team_id: str, task_type: str = "task") -> list[dict]:
    """
    TOOL: search_tasks_by_type
    Retrieve workspace tasks filtered by type.
    task_type must be one of: "task" or "subtask".

    Parameters
    ----------
    team_id   : str
    task_type : str
    """
    data = get(f"/team/{team_id}/task", {
        "include_closed": "true",
        "subtasks": "true" if task_type == "subtask" else "false",
        "types[]": task_type,
    })
    return [_fmt_task(t) for t in data.get("tasks", [])]


def search_tasks_by_tag(team_id: str, tags: list[str]) -> list[dict]:
    """
    TOOL: search_tasks_by_tag
    Retrieve workspace tasks that carry any of the given tags.

    Parameters
    ----------
    team_id : str
    tags    : list[str] – tag names, e.g. ["UX-quality"]
    """
    data = get(f"/team/{team_id}/task", {"tags[]": tags, "include_closed": "true"})
    return [_fmt_task(t) for t in data.get("tasks", [])]
