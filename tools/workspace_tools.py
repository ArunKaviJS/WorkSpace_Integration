"""
tools/workspace_tools.py
ClickUp workspace hierarchy tools.
Hierarchy: Workspace (Team) → Space → Folder → List → Task
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import CLICKUP_BASE_URL, CLICKUP_HEADERS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(endpoint: str, params: dict | None = None) -> Any:
    url = f"{CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.get(url, headers=CLICKUP_HEADERS, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Tool functions  (each returns a plain Python dict/list – JSON-serialisable)
# ---------------------------------------------------------------------------


def get_authorized_user() -> dict:
    """
    TOOL: get_authorized_user
    Returns info about the authenticated ClickUp user.
    """
    data = _get("/user")
    u = data.get("user", {})
    return {
        "id": u.get("id"),
        "username": u.get("username"),
        "email": u.get("email"),
        "color": u.get("color"),
        "profile_picture": u.get("profilePicture"),
    }


def get_workspaces() -> list[dict]:
    """
    TOOL: get_workspaces
    Lists all workspaces (teams) the authenticated user belongs to.
    """
    data = _get("/team")
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "color": t.get("color"),
            "avatar": t.get("avatar"),
            "members": [m["user"]["username"] for m in t.get("members", [])],
        }
        for t in data.get("teams", [])
    ]


def get_spaces(team_id: str) -> list[dict]:
    """
    TOOL: get_spaces
    Returns all spaces inside a workspace.

    Parameters
    ----------
    team_id : str  — workspace / team ID
    """
    data = _get(f"/team/{team_id}/space", {"archived": "false"})
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "private": s.get("private", False),
            "statuses": [st["status"] for st in s.get("statuses", [])],
        }
        for s in data.get("spaces", [])
    ]


def get_folders(space_id: str) -> list[dict]:
    """
    TOOL: get_folders
    Returns all folders inside a space.

    Parameters
    ----------
    space_id : str
    """
    data = _get(f"/space/{space_id}/folder", {"archived": "false"})
    return [
        {"id": f["id"], "name": f["name"], "task_count": f.get("task_count", 0)}
        for f in data.get("folders", [])
    ]


def get_lists(folder_id: str) -> list[dict]:
    """
    TOOL: get_lists
    Returns all lists inside a folder.

    Parameters
    ----------
    folder_id : str
    """
    data = _get(f"/folder/{folder_id}/list", {"archived": "false"})
    return [
        {
            "id": lst["id"],
            "name": lst["name"],
            "task_count": lst.get("task_count", 0),
            "status": lst.get("status", {}).get("status") if lst.get("status") else None,
        }
        for lst in data.get("lists", [])
    ]


def get_folderless_lists(space_id: str) -> list[dict]:
    """
    TOOL: get_folderless_lists
    Returns lists that live directly under a space (no folder).

    Parameters
    ----------
    space_id : str
    """
    data = _get(f"/space/{space_id}/list", {"archived": "false"})
    return [
        {
            "id": lst["id"],
            "name": lst["name"],
            "task_count": lst.get("task_count", 0),
        }
        for lst in data.get("lists", [])
    ]


def get_workspace_members(team_id: str) -> list[dict]:
    """
    TOOL: get_workspace_members
    Returns all members in the workspace (useful for task assignment).

    Parameters
    ----------
    team_id : str
    """
    data = _get(f"/team/{team_id}")
    team = data.get("team", {})
    return [
        {
            "id": m["user"]["id"],
            "username": m["user"]["username"],
            "email": m["user"]["email"],
            "role": m.get("role"),
        }
        for m in team.get("members", [])
    ]
