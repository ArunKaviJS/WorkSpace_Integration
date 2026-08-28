"""
bitbucket/deployment_tools.py
Bitbucket Deployments & Environments tools — list/get deployments, and
list/get/create/delete/update deployment environments.

Deleting an environment is HUMAN-GATED and requires an explicit
`confirmed: True` flag.

Every function returns plain JSON-serialisable data. Errors are raised as
BitbucketError and normalised by the agent dispatcher into
{"error": true, "message": ..., "status_code": ...}.
"""
from __future__ import annotations

from typing import Any

from bitbucket.bitbucket_http import _del, _get, _post, _workspace


def bitbucket_deployment_list(
    repo_slug: str,
    workspace: str = "",
    pagelen: int = 25,
) -> dict:
    """
    TOOL: bitbucket_deployment_list
    List deployments for a repository. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug : str
    workspace : str
    pagelen   : int – page size

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../deployments).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/deployments", {"pagelen": pagelen})


def bitbucket_deployment_get(
    repo_slug: str, deployment_uuid: str = "", workspace: str = ""
) -> dict:
    """
    TOOL: bitbucket_deployment_get
    Get details for a single deployment. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug        : str
    deployment_uuid  : str – deployment UUID
    workspace        : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API
    (GET .../deployments/{deployment_uuid}).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/deployments/{deployment_uuid}")


def bitbucket_environment_list(
    repo_slug: str,
    workspace: str = "",
    pagelen: int = 25,
) -> dict:
    """
    TOOL: bitbucket_environment_list
    List deployment environments for a repository. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug : str
    workspace : str
    pagelen   : int – page size

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../environments).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/environments", {"pagelen": pagelen})


def bitbucket_environment_get(
    repo_slug: str, environment_uuid: str = "", workspace: str = ""
) -> dict:
    """
    TOOL: bitbucket_environment_get
    Get details for a single deployment environment. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug         : str
    environment_uuid  : str – environment UUID
    workspace         : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API
    (GET .../environments/{environment_uuid}).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/environments/{environment_uuid}")


def bitbucket_environment_create(
    repo_slug: str,
    name: str,
    environment_type: str = "Production",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_environment_create
    Create a deployment environment for a repository. Scope: admin:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug        : str
    name             : str – environment name, e.g. "staging"
    environment_type : str – e.g. Production | Test | Staging (default "Production")
    workspace        : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (POST .../environments).
    """
    ws = workspace or _workspace()
    payload: dict[str, Any] = {"name": name}
    if environment_type:
        payload["environment_type"] = environment_type
    return _post(f"/repositories/{ws}/{repo_slug}/environments", payload)


def bitbucket_environment_delete(
    repo_slug: str,
    environment_uuid: str = "",
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: bitbucket_environment_delete
    Delete a deployment environment. HUMAN-GATED — requires confirmed=True.
    Scope: admin:pipeline:bitbucket.
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "bitbucket_environment_delete",
            "summary": f"Permanently delete environment {environment_uuid} in {ws}/{repo_slug}",
            "reason": (
                "Deleting an environment is destructive and affects deployments — "
                "pass confirmed=True to execute."
            ),
        }
    _del(f"/repositories/{ws}/{repo_slug}/environments/{environment_uuid}")
    return {
        "action": "bitbucket_environment_delete",
        "deleted": True,
        "repo": f"{ws}/{repo_slug}",
        "environment_uuid": environment_uuid,
    }


def bitbucket_environment_update(
    repo_slug: str,
    environment_uuid: str = "",
    update: dict | None = None,
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_environment_update
    Update a deployment environment. Scope: admin:pipeline:bitbucket.

    Update is implemented via the official "Update an environment" operation
    (POST .../environments/{environment_uuid}/changes).

    Parameters
    ----------
    repo_slug         : str
    environment_uuid  : str – environment UUID
    update            : dict – update payload, e.g.
                        {"name": "prod", "environment_type": "Production"}
    workspace         : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API.
    """
    ws = workspace or _workspace()
    payload: dict[str, Any] = update or {}
    return _post(
        f"/repositories/{ws}/{repo_slug}/environments/{environment_uuid}/changes",
        payload,
    )
