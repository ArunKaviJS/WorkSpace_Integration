"""
tools/comment_tools.py
Post and retrieve comments on ClickUp tasks.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import CLICKUP_BASE_URL, CLICKUP_HEADERS

logger = logging.getLogger(__name__)


def _post(endpoint: str, payload: dict) -> Any:
    url = f"{CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.post(url, headers=CLICKUP_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get(endpoint: str, params: dict | None = None) -> Any:
    url = f"{CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.get(url, headers=CLICKUP_HEADERS, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_task_comments(task_id: str) -> list[dict]:
    """
    TOOL: get_task_comments
    Fetch the most recent comments on a task.

    Parameters
    ----------
    task_id : str
    """
    data = _get(f"/task/{task_id}/comment")
    return [
        {
            "id": c["id"],
            "text": c.get("comment_text", ""),
            "author": (c.get("user") or {}).get("username"),
            "date": c.get("date"),
        }
        for c in data.get("comments", [])
    ]


def post_task_comment(task_id: str, comment_text: str, notify_all: bool = False) -> dict:
    """
    TOOL: post_task_comment
    Post a comment on a task.

    Parameters
    ----------
    task_id      : str
    comment_text : str
    notify_all   : bool
    """
    payload = {"comment_text": comment_text, "notify_all": notify_all}
    return _post(f"/task/{task_id}/comment", payload)
