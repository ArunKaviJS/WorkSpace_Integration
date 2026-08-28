"""
bitbucket/workspace_tools.py
Workspace membership tools — list workspace members.

Changing a workspace member's *role* (owner/admin/member) is NOT exposed by the
Bitbucket Cloud REST API. The `/workspaces/{ws}/permissions` endpoint is read-only
(GET list only); role assignment happens in the Atlassian administration
interface (admin.atlassian.com), outside the Cloud REST API. `update_workspace_member_role`
therefore returns a clear "not supported" message instead of issuing an invalid
HTTP request (previously it 404'd on a non-existent PUT endpoint).
"""
from __future__ import annotations

from bitbucket.bitbucket_http import _get, _workspace

_NOT_SUPPORTED_MESSAGE = (
    "Changing workspace member roles is not supported through the available "
    "Bitbucket API. Use the appropriate Atlassian administration interface/API."
)


def _normalize_uuid(user_id: str) -> str:
    """Strip surrounding braces so a braced UUID is never sent in a URL."""
    return (user_id or "").strip().strip("{}")


def list_workspace_members(workspace: str = "") -> list[dict]:
    """
    TOOL: list_workspace_members
    List all members (users) of a Bitbucket workspace together with their
    workspace-level role (owner / admin / member).

    Parameters
    ----------
    workspace : str
    """
    ws = workspace or _workspace()
    data = _get(f"/workspaces/{ws}/permissions", {"pagelen": 100})
    return [
        {
            "display_name": (u.get("user") or {}).get("display_name") or "",
            "email": (u.get("user") or {}).get("email") or "",
            "uuid": (u.get("user") or {}).get("uuid") or "",
            "account_id": (u.get("user") or {}).get("account_id") or "",
            "type": u.get("type") or "",
            "permission": u.get("permission") or "",
        }
        for u in data.get("values", [])
    ]


def update_workspace_member_role(
    selected_user_id: str,
    role: str,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: update_workspace_member_role
    Attempt to change a workspace member's role.

    NOTE: As of the current Bitbucket Cloud REST API there is NO supported
    endpoint to change a workspace member's role — `/workspaces/{ws}/permissions`
    is read-only (GET list). This tool normalizes the supplied user id (stripping
    any surrounding braces) and then returns a clear "not supported" error rather
    than calling a non-existent endpoint.

    Parameters
    ----------
    selected_user_id : str – member's workspace UUID or account_id
    role             : str – owner | admin | member
    workspace        : str
    confirmed        : bool
    """
    ws = workspace or _workspace()
    user_id = _normalize_uuid(selected_user_id)
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "update_workspace_member_role",
            "summary": f"Set member {user_id} role to '{role}' in workspace {ws}",
            "reason": (
                "Changing a workspace member's role affects workspace-wide access "
                "for the whole team — pass confirmed=True to execute."
            ),
        }
    return {
        "error": _NOT_SUPPORTED_MESSAGE,
        "action": "update_workspace_member_role",
        "user": user_id,
        "role": role,
        "workspace": ws,
    }


def bitbucket_workspace_list() -> dict:
    """
    TOOL: bitbucket_workspace_list
    List all workspaces accessible to the authenticated user, including whether
    the caller has admin permission on each. Scope: read:workspace:bitbucket.

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET /user/workspaces).
    """
    return _get("/user/workspaces")


def bitbucket_workspace_get(workspace: str = "") -> dict:
    """
    TOOL: bitbucket_workspace_get
    Get details for a single workspace (name, slug, uuid, is_private, etc.).

    Parameters
    ----------
    workspace : str – workspace slug or UUID (defaults to BITBUCKET_WORKSPACE)

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET /workspaces/{workspace}).
    """
    ws = workspace or _workspace()
    return _get(f"/workspaces/{ws}")
