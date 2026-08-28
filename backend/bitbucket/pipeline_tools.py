"""
bitbucket/pipeline_tools.py
Bitbucket Pipelines tools — list/get/run pipelines, steps and step logs, plus
failure-analysis helpers that correlate failed commit statuses / pipeline steps.

Every function returns plain JSON-serialisable data. Errors are raised as
BitbucketError and normalised by the agent dispatcher into
{"error": true, "message": ..., "status_code": ...}.
"""
from __future__ import annotations

from typing import Any

from bitbucket.bitbucket_http import _get, _post, _workspace


def bitbucket_pipeline_list(
    repo_slug: str,
    workspace: str = "",
    pagelen: int = 25,
) -> dict:
    """
    TOOL: bitbucket_pipeline_list
    List pipelines for a repository. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug : str
    workspace : str
    pagelen   : int – page size

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../pipelines).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/pipelines", {"pagelen": pagelen})


def bitbucket_pipeline_get(
    repo_slug: str, pipeline_uuid: str = "", workspace: str = ""
) -> dict:
    """
    TOOL: bitbucket_pipeline_get
    Get details for a single pipeline. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug      : str
    pipeline_uuid  : str – pipeline UUID, e.g. "a1b2c3d4-..."
    workspace      : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../pipelines/{pipeline_uuid}).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/pipelines/{pipeline_uuid}")


def bitbucket_pipeline_run(
    repo_slug: str,
    ref_type: str = "branch",
    ref_name: str = "",
    selector_type: str = "custom",
    selector_pattern: str = "**",
    variables: list[dict] | None = None,
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pipeline_run
    Trigger a pipeline for a repository. Scope: write:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug         : str
    ref_type          : str – branch | commit | pull_request (default branch)
    ref_name          : str – target branch name when ref_type=branch
    selector_type     : str – custom | branches | tags | pull-requests (default custom)
    selector_pattern  : str – selector pattern (default "**")
    variables         : list[dict] – optional pipeline variables, e.g.
                       [{"key": "DEPLOY", "value": "prod", "secured": false}]
    workspace         : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (POST .../pipelines).
    """
    ws = workspace or _workspace()
    target: dict[str, Any] = {"selector": {"type": selector_type, "pattern": selector_pattern}}
    if ref_type == "commit":
        target["commit"] = ref_name
    else:
        target["ref_type"] = ref_type
        if ref_name:
            target["ref_name"] = ref_name
    payload: dict[str, Any] = {"target": target}
    if variables:
        payload["variables"] = variables
    return _post(f"/repositories/{ws}/{repo_slug}/pipelines", payload)


def bitbucket_pipeline_steps(
    repo_slug: str,
    pipeline_uuid: str = "",
    workspace: str = "",
    pagelen: int = 25,
) -> dict:
    """
    TOOL: bitbucket_pipeline_steps
    List the steps of a pipeline. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug     : str
    pipeline_uuid : str
    workspace     : str
    pagelen       : int

    Returns
    -------
    Raw parsed JSON from the Bitbucket API (GET .../pipelines/{uuid}/steps).
    """
    ws = workspace or _workspace()
    return _get(
        f"/repositories/{ws}/{repo_slug}/pipelines/{pipeline_uuid}/steps",
        {"pagelen": pagelen},
    )


def bitbucket_pipeline_step_get(
    repo_slug: str,
    pipeline_uuid: str = "",
    step_uuid: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pipeline_step_get
    Get details for a single pipeline step. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug     : str
    pipeline_uuid : str
    step_uuid     : str
    workspace     : str

    Returns
    -------
    Raw parsed JSON from the Bitbucket API
    (GET .../pipelines/{uuid}/steps/{step_uuid}).
    """
    ws = workspace or _workspace()
    return _get(f"/repositories/{ws}/{repo_slug}/pipelines/{pipeline_uuid}/steps/{step_uuid}")


def bitbucket_pipeline_step_log(
    repo_slug: str,
    pipeline_uuid: str = "",
    step_uuid: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_pipeline_step_log
    Get the log for a pipeline step. Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug     : str
    pipeline_uuid : str
    step_uuid     : str
    workspace     : str

    Returns
    -------
    Raw log content (text) for the pipeline step.
    """
    ws = workspace or _workspace()
    import requests

    from config.settings import BITBUCKET_AUTH, BITBUCKET_BASE_URL
    from bitbucket.bitbucket_http import BitbucketError

    url = (
        f"{BITBUCKET_BASE_URL}/repositories/{ws}/{repo_slug}/pipelines/"
        f"{pipeline_uuid}/steps/{step_uuid}/log"
    )
    resp = requests.get(url, auth=BITBUCKET_AUTH, timeout=30)
    if not resp.ok:
        raise BitbucketError(resp.status_code, str(resp.text or "").strip())
    return {
        "workspace": ws,
        "repo": repo_slug,
        "pipeline_uuid": pipeline_uuid,
        "step_uuid": step_uuid,
        "log": resp.text,
    }


def bitbucket_analyze_pr_commit_failures(
    repo_slug: str,
    pr_id: int | None = None,
    workspace: str = "",
) -> dict:
    """
    TOOL: bitbucket_analyze_pr_commit_failures
    Analyze failed commit-status checks (e.g. failed pipelines) on a pull request.
    Scope: read:pullrequest:bitbucket, read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug : str
    pr_id     : int
    workspace : str

    Returns
    -------
    dict summarizing the failed commit statuses on the PR, with reasons when possible.
    """
    ws = workspace or _workspace()
    statuses = _get(
        f"/repositories/{ws}/{repo_slug}/pullrequests/{pr_id}/statuses",
        {"pagelen": 100},
    )
    values = statuses.get("values", [])
    failed = [
        {
            "name": s.get("name"),
            "state": s.get("state"),
            "description": s.get("description"),
            "key": s.get("key"),
            "type": s.get("type"),
        }
        for s in values
        if s.get("state") in ("FAILED", "ERROR")
    ]
    return {
        "workspace": ws,
        "repo": repo_slug,
        "pr_id": pr_id,
        "total_checks": len(values),
        "failed_checks": failed,
        "summary": (
            f"{len(failed)} of {len(values)} commit checks failed on PR #{pr_id}."
        ),
    }


def bitbucket_analyze_pipeline_step_failure(
    repo_slug: str,
    pipeline_uuid: str = "",
    step_uuid: str = "",
    workspace: str = "",
    log_lines: int = 200,
) -> dict:
    """
    TOOL: bitbucket_analyze_pipeline_step_failure
    Analyze why a pipeline step failed by combining the step state and its log.
    Scope: read:pipeline:bitbucket.

    Parameters
    ----------
    repo_slug     : str
    pipeline_uuid : str
    step_uuid     : str
    workspace     : str
    log_lines     : int – number of trailing log lines to surface (default 200)

    Returns
    -------
    dict with the step state and the tail of its log for diagnosis.
    """
    ws = workspace or _workspace()
    step = bitbucket_pipeline_step_get(
        repo_slug=repo_slug,
        pipeline_uuid=pipeline_uuid,
        step_uuid=step_uuid,
        workspace=ws,
    )
    state = (step.get("state") or {}).get("name") or step.get("state")
    log_data = bitbucket_pipeline_step_log(
        repo_slug=repo_slug,
        pipeline_uuid=pipeline_uuid,
        step_uuid=step_uuid,
        workspace=ws,
    )
    log_text = log_data.get("log", "")
    lines = [line for line in log_text.splitlines() if line.strip()]
    tail = lines[-log_lines:] if lines else []
    return {
        "workspace": ws,
        "repo": repo_slug,
        "pipeline_uuid": pipeline_uuid,
        "step_uuid": step_uuid,
        "step_state": state,
        "step_name": (step.get("name") or ""),
        "log_tail": tail,
        "log_line_count": len(lines),
        "summary": (
            f"Step {step_uuid} finished with state '{state}'. See log tail "
            f"(last {min(len(tail), log_lines)} lines) for the failure reason."
        ),
    }
