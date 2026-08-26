"""
tools/relation_tools.py
Task relationships: links between tasks and blocking dependencies.
"""
from __future__ import annotations

from tools.http import delete as http_delete, post, put


def add_task_link(task_id: str, linked_task_id: str) -> dict:
    """
    TOOL: add_task_link
    Relate two tasks by linking them (no dependency — just a link).

    Parameters
    ----------
    task_id         : str
    linked_task_id  : str
    """
    put(f"/task/{task_id}/link/{linked_task_id}")
    return {"linked": [task_id, linked_task_id]}


def remove_task_link(task_id: str, linked_task_id: str) -> dict:
    """
    TOOL: remove_task_link
    Remove the link between two tasks.

    Parameters
    ----------
    task_id        : str
    linked_task_id : str
    """
    http_delete(f"/task/{task_id}/link/{linked_task_id}")
    return {"unlinked": [task_id, linked_task_id]}


def add_dependency(task_id: str, depends_on: str | None = None, dependency_of: str | None = None) -> dict:
    """
    TOOL: add_dependency
    Create a dependency between two tasks. Pass exactly one direction:
      depends_on    → this task is BLOCKED BY the given task
      dependency_of → this task BLOCKS the given task

    Parameters
    ----------
    task_id       : str
    depends_on    : str | None – blocker task ID
    dependency_of : str | None – blocked task ID
    """
    if bool(depends_on) == bool(dependency_of):
        raise ValueError("Pass exactly one of depends_on or dependency_of")
    payload: dict = {}
    if depends_on:
        payload["depends_on"] = depends_on
    else:
        payload["dependency_of"] = dependency_of
    post(f"/task/{task_id}/dependency", payload)
    return {"dependency_created": {"task": task_id, **payload}}


def remove_dependency(task_id: str, depends_on: str | None = None, dependency_of: str | None = None) -> dict:
    """
    TOOL: remove_dependency
    Remove a dependency between two tasks. Pass exactly one direction.

    Parameters
    ----------
    task_id       : str
    depends_on    : str | None
    dependency_of : str | None
    """
    if bool(depends_on) == bool(dependency_of):
        raise ValueError("Pass exactly one of depends_on or dependency_of")
    params = {"depends_on": depends_on} if depends_on else {"dependency_of": dependency_of}
    http_delete(f"/task/{task_id}/dependency", params=params)
    return {"dependency_removed": {"task": task_id, **params}}
