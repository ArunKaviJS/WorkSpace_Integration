"""
tools/tag_tools.py
Add / remove tags on tasks.
"""
from __future__ import annotations

from tools.http import delete as http_delete, post


def add_tag_to_task(task_id: str, tag_name: str) -> dict:
    """
    TOOL: add_tag_to_task
    Apply an existing tag to a task. Tag must already exist in the space.

    Parameters
    ----------
    task_id  : str
    tag_name : str – e.g. "Urgent" (spaces are encoded as %20)
    """
    post(f"/task/{task_id}/tag/{tag_name.replace(' ', '%20')}")
    return {"task_id": task_id, "tag_added": tag_name}


def remove_tag_from_task(task_id: str, tag_name: str) -> dict:
    """
    TOOL: remove_tag_from_task
    Remove a tag from a task.

    Parameters
    ----------
    task_id  : str
    tag_name : str
    """
    http_delete(f"/task/{task_id}/tag/{tag_name.replace(' ', '%20')}")
    return {"task_id": task_id, "tag_removed": tag_name}
