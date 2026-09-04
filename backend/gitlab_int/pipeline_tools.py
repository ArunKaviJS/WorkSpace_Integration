"""
gitlab_int/pipeline_tools.py
Pipeline tools — list pipelines, inspect one, and list its jobs.

Read-only. Handy for the chat agent ("why did the last pipeline on main fail?").
"""
from __future__ import annotations

from typing import Any

from gitlab_int.gitlab_client import get_project, gl_call, list_bounded


def _fmt_pipeline(p: Any) -> dict:
    a = p if isinstance(p, dict) else (getattr(p, "attributes", {}) or {})
    return {
        "id": a.get("id"),
        "iid": a.get("iid"),
        "status": a.get("status"),
        "source": a.get("source"),
        "ref": a.get("ref"),
        "sha": a.get("sha"),
        "web_url": a.get("web_url"),
        "created_at": a.get("created_at"),
        "updated_at": a.get("updated_at"),
    }


@gl_call
def gitlab_pipeline_list(project_id: str, ref: str = "", limit: int = 20) -> dict:
    """
    TOOL: gitlab_pipeline_list
    List recent pipelines for a project (optionally filtered by ref).
    """
    project = get_project(project_id)
    kwargs: dict[str, Any] = {"order_by": "id", "sort": "desc"}
    if ref:
        kwargs["ref"] = ref
    pipelines = list_bounded(project.pipelines, limit=limit, **kwargs)
    return {
        "project": project.attributes.get("path_with_namespace"),
        "count": len(pipelines),
        "pipelines": [_fmt_pipeline(p) for p in pipelines],
    }


@gl_call
def gitlab_pipeline_get(project_id: str, pipeline_id: int) -> dict:
    """
    TOOL: gitlab_pipeline_get
    Get one pipeline with its overall status and duration.
    """
    project = get_project(project_id)
    p = project.pipelines.get(pipeline_id)
    out = _fmt_pipeline(p)
    out["duration"] = p.attributes.get("duration")
    out["coverage"] = p.attributes.get("coverage")
    return out


@gl_call
def gitlab_pipeline_jobs(project_id: str, pipeline_id: int, limit: int = 50) -> dict:
    """
    TOOL: gitlab_pipeline_jobs
    List the jobs of a pipeline with their per-stage status.
    """
    project = get_project(project_id)
    p = project.pipelines.get(pipeline_id)
    jobs = list_bounded(p.jobs, limit=limit)
    return {
        "project": project.attributes.get("path_with_namespace"),
        "pipeline_id": pipeline_id,
        "count": len(jobs),
        "jobs": [
            {
                "id": j.attributes.get("id"),
                "name": j.attributes.get("name"),
                "stage": j.attributes.get("stage"),
                "status": j.attributes.get("status"),
                "allow_failure": j.attributes.get("allow_failure"),
                "web_url": j.attributes.get("web_url"),
                "failure_reason": j.attributes.get("failure_reason"),
            }
            for j in jobs
        ],
    }
