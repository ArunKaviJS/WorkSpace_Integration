"""
tools/bulk_tools.py
Bulk create / update tasks. ClickUp v2 has no native bulk endpoint, so these
loop the single-task API while reporting per-item success/failure.
"""
from __future__ import annotations

from tools.task_tools import create_task, update_task


def create_bulk_tasks(
    list_id: str,
    names: list[str],
    assignee_ids: list[int] | None = None,
    priority: int | None = None,
    due_date_epoch_ms: int | None = None,
) -> dict:
    """
    TOOL: create_bulk_tasks
    Create multiple tasks in one list with shared defaults.
    Example: names=["Send welcome email", "Schedule orientation"].

    Parameters
    ----------
    list_id           : str
    names             : list[str] – one entry per new task
    assignee_ids      : list[int] | None – applied to every task
    priority          : int | None – applied to every task
    due_date_epoch_ms : int | None – applied to every task
    """
    created, failed = [], []
    for name in names:
        try:
            created.append(create_task(list_id, name=name, assignee_ids=assignee_ids,
                                       priority=priority, due_date_epoch_ms=due_date_epoch_ms))
        except Exception as exc:  # noqa: BLE001
            failed.append({"name": name, "error": str(exc)})
    return {"created_count": len(created), "created": created, "failed": failed}


def update_bulk_tasks(task_ids: list[str], fields: dict) -> dict:
    """
    TOOL: update_bulk_tasks
    Apply the same field changes to many tasks at once.
    Example: fields={"status": "In Review"}, task_ids=[...].

    Parameters
    ----------
    task_ids : list[str]
    fields   : dict – e.g. {"status": "...", "priority": 2, "due_date": ...}
    """
    updated, failed = [], []
    for tid in task_ids:
        try:
            updated.append(update_task(tid, fields))
        except Exception as exc:  # noqa: BLE001
            failed.append({"task_id": tid, "error": str(exc)})
    return {"updated_count": len(updated), "updated": updated, "failed": failed}
