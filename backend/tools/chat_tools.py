"""
tools/chat_tools.py
ClickUp Chat (v3 API): list channels and send messages.
Requires OAuth-app token for v3 in most workspaces.
"""
from __future__ import annotations

from tools.http import V3_URL, get, post


def get_chat_channels(workspace_id: str) -> list[dict]:
    """
    TOOL: get_chat_channels
    List all Chat channels (views) in a workspace.

    Parameters
    ----------
    workspace_id : str – workspace/team ID
    """
    data = get(f"/workspaces/{workspace_id}/chat/channels", base=V3_URL)
    return [
        {
            "id": c["id"],
            "name": c.get("name"),
            "type": c.get("type"),
            "visibility": c.get("visibility"),
        }
        for c in data.get("channels", [])
    ]


def send_chat_message(workspace_id: str, channel_id: str, message_text: str) -> dict:
    """
    TOOL: send_chat_message
    Post a message to a specific Chat channel.

    Parameters
    ----------
    workspace_id : str
    channel_id   : str
    message_text : str – e.g. "Team lunch at 1 PM today."
    """
    payload = {
        "content": {"type": "doc", "data": {"nodes": [
            {"type": "paragraph", "content": [{"type": "text", "text": message_text}]}
        ]}},
    }
    return post(
        f"/workspaces/{workspace_id}/chat/channels/{channel_id}/messages",
        payload,
        base=V3_URL,
    )
