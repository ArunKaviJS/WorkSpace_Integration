"""
tools/member_tools.py
Member lookup helpers used before assignment.
"""
from __future__ import annotations

from tools.workspace_tools import get_workspace_members


def find_member_by_name(team_id: str, query: str) -> list[dict]:
    """
    TOOL: find_member_by_name
    Search workspace members by name OR email.

    Parameters
    ----------
    team_id : str
    query   : str – e.g. "David Smith" or "david@corp.com"
    """
    q = query.lower()
    members = get_workspace_members(team_id)
    return [
        m
        for m in members
        if q in m["username"].lower() or q in (m.get("email") or "").lower()
    ]


def resolve_assignees(team_id: str, names: list[str]) -> dict:
    """
    TOOL: resolve_assignees
    Resolve human names/emails into ClickUp user IDs before assigning tasks.
    Unmatched names are reported back so the agent can ask the user.

    Parameters
    ----------
    team_id : str
    names   : list[str] – e.g. ["Mark", "Sarah"]
    """
    members = get_workspace_members(team_id)
    resolved, unresolved = {}, []
    for name in names:
        n = name.lower()
        match = next(
            (
                m
                for m in members
                if n == m["username"].lower()
                or n == (m.get("email") or "").lower()
                or n in m["username"].lower()
            ),
            None,
        )
        if match:
            resolved[name] = {"id": match["id"], "username": match["username"]}
        else:
            unresolved.append(name)
    return {"resolved": resolved, "unresolved": unresolved}
