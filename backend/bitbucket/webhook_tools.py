"""
bitbucket/webhook_tools.py
Webhook tools — list, add and remove repository webhooks.

remove_webhook stops event delivery and is HUMAN-GATED, requiring an explicit
`confirmed: True` flag.
"""
from __future__ import annotations

from bitbucket.bitbucket_http import _del, _get, _post, _workspace


def list_webhooks(repo_slug: str, workspace: str = "") -> list[dict]:
    """
    TOOL: list_webhooks
    List all webhooks configured on a repository.

    Parameters
    ----------
    repo_slug : str
    workspace : str
    """
    data = _get(f"/repositories/{workspace or _workspace()}/{repo_slug}/hooks")
    return [
        {
            "uuid": h.get("uuid"),
            "url": h.get("url"),
            "description": h.get("description"),
            "active": h.get("active"),
            "events": h.get("events", []),
        }
        for h in data.get("values", [])
    ]


def add_webhook(
    repo_slug: str,
    url: str,
    events: list[str] | None = None,
    description: str = "",
    workspace: str = "",
) -> dict:
    """
    TOOL: add_webhook
    Add a webhook to a repository for the given event types.

    Parameters
    ----------
    repo_slug    : str
    url          : str – callback URL for the webhook
    events       : list[str] – e.g. ["repo:push", "pullrequest:created"]
    description  : str
    workspace    : str
    """
    payload = {"url": url, "events": events or ["repo:push"]}
    if description:
        payload["description"] = description
    data = _post(
        f"/repositories/{workspace or _workspace()}/{repo_slug}/hooks",
        payload,
    )
    return {
        "action": "add_webhook",
        "uuid": data.get("uuid"),
        "url": data.get("url"),
        "events": data.get("events", []),
        "active": data.get("active"),
    }


def remove_webhook(
    repo_slug: str,
    hook_uuid: str,
    workspace: str = "",
    confirmed: bool = False,
) -> dict:
    """
    TOOL: remove_webhook
    Delete a webhook from a repository. HUMAN-GATED — requires confirmed=True.

    Parameters
    ----------
    repo_slug   : str
    hook_uuid   : str – the webhook UUID (from list_webhooks)
    workspace   : str
    confirmed   : bool
    """
    ws = workspace or _workspace()
    if not confirmed:
        return {
            "needs_confirmation": True,
            "action": "remove_webhook",
            "summary": f"Remove webhook {hook_uuid} from {ws}/{repo_slug}",
            "reason": "Removing a webhook stops events from being delivered — pass confirmed=True to execute.",
        }
    _del(f"/repositories/{ws}/{repo_slug}/hooks/{hook_uuid}")
    return {
        "action": "remove_webhook",
        "deleted": True,
        "hook_uuid": hook_uuid,
        "repo": f"{ws}/{repo_slug}",
    }
