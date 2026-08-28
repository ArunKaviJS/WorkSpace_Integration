"""
bitbucket/property_tools.py
Application-property tools — read / write / delete JSON properties attached to
a repository, a pull request, or a commit (used by add-ons and integrations).

delete_application_properties is destructive and is HUMAN-GATED, requiring an
explicit `confirmed: True` flag.
"""
from __future__ import annotations

from typing import Any

from bitbucket.bitbucket_http import _del, _get, _put, _workspace


def _property_path(
    ws: str, repo_slug: str, scope: str, pr_id: str, commit: str, name: str
) -> str:
    """Build the Bitbucket application-properties endpoint path for a scope."""
    base = f"/repositories/{ws}/{repo_slug}"
    if scope == "pull_request":
        return f"{base}/pullrequests/{pr_id}/properties/{name}/"
    if scope == "commit":
        return f"{base}/commit/{commit}/properties/{name}/"
    return f"{base}/properties/{name}/"


def get_application_properties(
    repo_slug: str,
    app_key: str,
    name: str,
    scope: str = "repository",
    pr_id: str = "",
    commit: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: get_application_properties
    Read an application property for a commit / repository / pull request.

    Parameters
    ----------
    repo_slug : str
    app_key   : str – the application / add-on key
    name      : str – property name
    scope     : str – repository | pull_request | commit
    pr_id     : str – required when scope=pull_request
    commit    : str – required when scope=commit
    workspace : str
    """
    ws = workspace or _workspace()
    path = _property_path(ws, repo_slug, scope, pr_id, commit, name)
    data = _get(path)
    return {
        "action": "get_application_properties",
        "scope": scope,
        "app_key": app_key,
        "name": name,
        "value": data,
    }


def update_application_properties(
    repo_slug: str,
    app_key: str,
    name: str,
    value: Any,
    scope: str = "repository",
    pr_id: str = "",
    commit: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: update_application_properties
    Update (PUT) an application property for a commit / repository / PR.

    Parameters
    ----------
    repo_slug : str
    app_key   : str
    name      : str
    value     : any – the JSON value to store
    scope     : str – repository | pull_request | commit
    pr_id     : str
    commit    : str
    workspace : str
    """
    ws = workspace or _workspace()
    path = _property_path(ws, repo_slug, scope, pr_id, commit, name)
    data = _put(path, {"value": value})
    return {
        "action": "update_application_properties",
        "scope": scope,
        "name": name,
        "updated": True,
        "data": data,
    }


def delete_application_properties(
    repo_slug: str,
    app_key: str,
    name: str,
    scope: str = "repository",
    pr_id: str = "",
    commit: str = "",
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: delete_application_properties
    Delete an application property for a commit / repository / PR.
    HUMAN-GATED — requires confirmed=True.

    Parameters
    ----------
    repo_slug : str
    app_key   : str
    name      : str
    scope     : str – repository | pull_request | commit
    pr_id     : str
    commit    : str
    workspace : str
    confirmed : bool
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "delete_application_properties",
            "summary": f"Delete application property '{name}' ({app_key}) on {scope} in {ws}/{repo_slug}",
            "reason": "Deleting a property is irreversible — pass confirmed=True to execute.",
        }
    path = _property_path(ws, repo_slug, scope, pr_id, commit, name)
    _del(path)
    return {
        "action": "delete_application_properties",
        "deleted": True,
        "scope": scope,
        "name": name,
    }
