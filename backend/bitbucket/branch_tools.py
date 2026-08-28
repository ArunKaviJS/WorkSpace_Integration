"""
bitbucket/branch_tools.py
Branch tools — create branches and set branch restrictions/permissions.

set_branch_permission affects the whole team and is HUMAN-GATED, requiring an
explicit `confirmed: True` flag.
"""
from __future__ import annotations

from typing import Any

from bitbucket.bitbucket_http import _post, _workspace


def create_branch(
    repo_slug: str,
    branch_name: str,
    from_commit: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: create_branch
    Create a branch from a given commit SHA (or the default branch if omitted).

    Parameters
    ----------
    repo_slug   : str
    branch_name : str – new branch name
    from_commit : str – source commit SHA
    workspace   : str
    """
    payload: dict[str, Any] = {"name": branch_name}
    if from_commit:
        payload["target"] = {"hash": from_commit}
    data = _post(f"/repositories/{workspace or _workspace()}/{repo_slug}/refs/branches", payload)
    return {
        "name": data.get("name"),
        "target": (data.get("target") or {}).get("hash"),
        "repo": f"{workspace or _workspace()}/{repo_slug}",
    }


def set_branch_permission(
    repo_slug: str,
    branch_pattern: str,
    kind: str,
    value: str,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: set_branch_permission
    Set branch restrictions/permissions for a repository. HUMAN-GATED.

    Parameters
    ----------
    repo_slug       : str
    branch_pattern  : str – e.g. "main", "release/*"
    kind            : str – push | delete | require_tasks_to_be_completed | require_passing_builds_to_merge etc.
    value           : str – the restriction value / flat string
    workspace       : str
    confirmed       : bool
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "set_branch_permission",
            "summary": f"Set branch restriction '{kind}' on '{branch_pattern}' in {ws}/{repo_slug}",
            "reason": "Changing branch permissions affects the whole team — pass confirmed=True to execute.",
        }
    # Bitbucket branch restrictions API (v2.0)
    payload: dict[str, Any] = {
        "kind": kind,
        "pattern": branch_pattern,
    }
    if value:
        payload["value"] = value
    data = _post(f"/repositories/{ws}/{repo_slug}/branch-restrictions", payload)
    return {
        "action": "set_branch_permission",
        "restriction_id": data.get("id"),
        "kind": data.get("kind"),
        "pattern": data.get("pattern"),
        "branching_model": None,
    }
