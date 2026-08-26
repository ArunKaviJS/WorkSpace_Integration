"""
tools/list_tools.py
List & Folder management, moving tasks between lists, full workspace hierarchy.
"""
from __future__ import annotations

from tools.http import get, post, put


# ── Task ↔ List movement ───────────────────────────────────────────────────

def move_task_to_list(list_id: str, task_id: str) -> dict:
    """
    TOOL: move_task_to_list
    Move a task to a new home list (removes it from the old one).

    Parameters
    ----------
    list_id : str – destination list
    task_id : str
    """
    data = post(f"/list/{list_id}/task/{task_id}")
    return {"moved": task_id, "to_list": list_id, "result": data}


def add_task_to_list(list_id: str, task_id: str) -> dict:
    """
    TOOL: add_task_to_list
    Add a task to another list while keeping it in its current list.

    Parameters
    ----------
    list_id : str – additional list
    task_id : str
    """
    return post(f"/task/{task_id}/list/{list_id}")


# ── Folder CRUD ────────────────────────────────────────────────────────────

def create_folder(space_id: str, name: str) -> dict:
    """
    TOOL: create_folder
    Create a new folder inside a space.

    Parameters
    ----------
    space_id : str
    name     : str – e.g. "Q1 Projects"
    """
    return post(f"/space/{space_id}/folder", {"name": name})


def update_folder(folder_id: str, name: str) -> dict:
    """
    TOOL: update_folder
    Rename or modify an existing folder.

    Parameters
    ----------
    folder_id : str
    name      : str – new name
    """
    return put(f"/folder/{folder_id}", {"name": name})


def get_folder_details(folder_id: str) -> dict:
    """
    TOOL: get_folder_details
    Get a single folder including the lists it contains.

    Parameters
    ----------
    folder_id : str
    """
    data = get(f"/folder/{folder_id}")
    return {
        "id": data["id"],
        "name": data["name"],
        "lists": [
            {"id": l["id"], "name": l["name"], "task_count": l.get("task_count", 0)}
            for l in data.get("lists", [])
        ],
    }


# ── List CRUD ──────────────────────────────────────────────────────────────

def create_list(name: str, space_id: str | None = None, folder_id: str | None = None) -> dict:
    """
    TOOL: create_list
    Create a new list — either inside a folder (folder_id) or directly
    under a space without a folder (space_id). Pass exactly one parent.

    Parameters
    ----------
    name      : str – e.g. "Sprint 4 Planning"
    space_id  : str | None
    folder_id : str | None
    """
    if bool(space_id) == bool(folder_id):
        raise ValueError("Pass exactly one of space_id or folder_id")
    payload = {"name": name}
    if folder_id:
        return post(f"/folder/{folder_id}/list", payload)
    return post(f"/space/{space_id}/list", payload)


def update_list(list_id: str, fields: dict) -> dict:
    """
    TOOL: update_list
    Modify list settings — e.g. {"name": "Approved Ideas"}.

    Parameters
    ----------
    list_id : str
    fields  : dict – updatable keys: name, content, due_date_time, status...
    """
    return put(f"/list/{list_id}", fields)


def get_list_details(list_id: str) -> dict:
    """
    TOOL: get_list_details
    Get settings and custom statuses for a single list.

    Parameters
    ----------
    list_id : str
    """
    data = get(f"/list/{list_id}")
    statuses = [s.get("status") for s in data.get("statuses", [])]
    return {
        "id": data["id"],
        "name": data["name"],
        "content": data.get("content"),
        "statuses": statuses,
        "task_count": data.get("task_count"),
    }


# ── Full workspace hierarchy ───────────────────────────────────────────────

def get_workspace_hierarchy(team_id: str) -> dict:
    """
    TOOL: get_workspace_hierarchy
    Retrieve the FULL structure of a workspace: every Space with its
    Folders and Lists (including folderless lists).

    Parameters
    ----------
    team_id : str
    """
    result: dict = {"workspace_id": team_id, "spaces": []}
    for space in get(f"/team/{team_id}/space", {"archived": "false"}).get("spaces", []):
        entry = {"id": space["id"], "name": space["name"], "folders": [], "lists": []}

        for lst in get(f"/space/{space['id']}/list", {"archived": "false"}).get("lists", []):
            entry["lists"].append({"id": lst["id"], "name": lst["name"]})

        for folder in get(f"/space/{space['id']}/folder", {"archived": "false"}).get("folders", []):
            f_entry = {"id": folder["id"], "name": folder["name"], "lists": []}
            for lst in get(f"/folder/{folder['id']}/list", {"archived": "false"}).get("lists", []):
                f_entry["lists"].append({"id": lst["id"], "name": lst["name"]})
            entry["folders"].append(f_entry)

        result["spaces"].append(entry)
    return result
