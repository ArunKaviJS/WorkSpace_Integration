"""
tools/attachment_tools.py
Upload and attach local files to tasks.
"""
from __future__ import annotations

import os

from tools.http import request


def attach_file_to_task(task_id: str, file_path: str) -> dict:
    """
    TOOL: attach_file_to_task
    Upload and attach a file (document, image, ZIP...) to a task.

    Parameters
    ----------
    task_id   : str
    file_path : str – absolute path to the local file to upload
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)
    with open(file_path, "rb") as fh:
        resp = request(
            "POST",
            f"/task/{task_id}/attachment",
            files={"file": (os.path.basename(file_path), fh)},
        )
    return {"attached": os.path.basename(file_path), "task_id": task_id, "response": resp}
