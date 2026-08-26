"""
tools/status_time_tools.py
Time-in-status reporting for single tasks and whole lists.
"""
from __future__ import annotations

from tools.http import get


def get_task_time_in_status(task_id: str) -> dict:
    """
    TOOL: get_task_time_in_status
    How long has this task spent in each status?

    Parameters
    ----------
    task_id : str
    """
    return get(f"/task/{task_id}/metric/time_in_status")


def get_list_time_in_status(list_id: str) -> dict:
    """
    TOOL: get_list_time_in_status
    Time-in-status metrics aggregated over tasks in a list — answers
    questions like "how long do tasks usually spend in QA review?".

    Parameters
    ----------
    list_id : str
    """
    return get(f"/list/{list_id}/metric/time_in_status")
