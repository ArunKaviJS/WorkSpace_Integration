"""
tools/time_tracking_tools.py
Time tracking: entries, start/stop timers, manual logs.
Requires a ClickUp Team/Business+ plan for the time-tracking API.
"""
from __future__ import annotations

from tools.http import get, post


def get_task_time_entries(team_id: str, task_id: str) -> list[dict]:
    """
    TOOL: get_task_time_entries
    Retrieve all time log entries for one task.

    Parameters
    ----------
    team_id : str – workspace ID
    task_id : str
    """
    data = get(f"/team/{team_id}/time_entries", {"task_id": task_id})
    return [
        {
            "id": e["id"],
            "task_id": e.get("task", {}).get("id"),
            "duration_ms": e.get("duration"),
            "start": e.get("start"),
            "end": e.get("end"),
            "user": (e.get("user") or {}).get("username"),
        }
        for e in data.get("data", [])
    ]


def get_time_entries_summary(team_id: str, task_ids: list[str]) -> dict:
    """
    TOOL: get_time_entries_summary
    Total tracked time across multiple tasks — pass all task IDs of a
    Space/Folder/List to answer "how much time have we spent on this list?".

    Parameters
    ----------
    team_id  : str
    task_ids : list[str]
    """
    total_ms = 0
    per_task: dict[str, int] = {}
    for tid in task_ids:
        data = get(f"/team/{team_id}/time_entries", {"task_id": tid})
        t_ms = sum(e.get("duration") or 0 for e in data.get("data", []))
        per_task[tid] = t_ms
        total_ms += t_ms
    return {
        "total_ms": total_ms,
        "total_hours": round(total_ms / 3_600_000, 2),
        "per_task_ms": per_task,
    }


def start_time_tracking(team_id: str, task_id: str) -> dict:
    """
    TOOL: start_time_tracking
    Start the timer on a task for the current authenticated user.

    Parameters
    ----------
    team_id : str
    task_id : str – ClickUp accepts "tid" as task_id here too
    """
    return post(f"/team/{team_id}/time_entries/start", {"tid": task_id})


def stop_time_tracking(team_id: str) -> dict:
    """
    TOOL: stop_time_tracking
    Stop the currently running timer for the authenticated user.

    Parameters
    ----------
    team_id : str
    """
    return post(f"/team/{team_id}/time_entries/stop")


def add_time_entry(team_id: str, task_id: str, start_epoch_ms: int, duration_ms: int) -> dict:
    """
    TOOL: add_time_entry
    Manually log a block of time to a task.

    Parameters
    ----------
    team_id        : str
    task_id        : str
    start_epoch_ms : int – entry start in Unix ms
    duration_ms    : int – e.g. 7200000 for 2 hours
    """
    return post(f"/team/{team_id}/time_entries",
                {"tid": task_id, "start": start_epoch_ms, "duration": duration_ms})


def get_current_time_entry(team_id: str) -> dict | None:
    """
    TOOL: get_current_time_entry
    Check whether the current user has a timer running; if so return it.

    Parameters
    ----------
    team_id : str
    """
    data = get(f"/team/{team_id}/time_entries/current")
    entry = data.get("data")
    if not entry:
        return None
    return {
        "task_id": (entry.get("task") or {}).get("id"),
        "task_name": (entry.get("task") or {}).get("name"),
        "start": entry.get("start"),
        "duration_so_far_ms": entry.get("duration"),
    }
