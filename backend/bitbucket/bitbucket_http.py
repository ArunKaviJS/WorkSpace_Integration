"""
bitbucket/bitbucket_http.py
Shared HTTP plumbing + response normalizers for the Bitbucket tool modules.

Every Bitbucket tool talks to https://api.bitbucket.org/2.0/ using HTTP Basic
Auth with the `email:api_token` credential pair (settings.BITBUCKET_AUTH).

The concrete tool functions live in sibling modules (repos_tools, pr_tools,
branch_tools, webhook_tools, property_tools) which import the helpers here.
Keeping HTTP + shaping in one place avoids duplicating auth/formatting logic.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import BITBUCKET_AUTH, BITBUCKET_BASE_URL, BITBUCKET_HEADERS, BITBUCKET_WORKSPACE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared HTTP helpers
# ---------------------------------------------------------------------------


def _request(
    method: str,
    endpoint: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> Any:
    url = f"{BITBUCKET_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.request(
        method,
        url,
        auth=BITBUCKET_AUTH,
        headers=BITBUCKET_HEADERS,
        params=params or {},
        json=json_body,
        timeout=30,
    )
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


def _get(endpoint: str, params: dict | None = None) -> Any:
    return _request("GET", endpoint, params=params)


def _post(endpoint: str, payload: dict | None = None, params: dict | None = None) -> Any:
    return _request("POST", endpoint, json_body=payload, params=params)


def _put(endpoint: str, payload: dict | None = None) -> Any:
    return _request("PUT", endpoint, json_body=payload)


def _post_form(endpoint: str, data: dict) -> Any:
    """POST with form-encoded data (used by the source-content write API)."""
    url = f"{BITBUCKET_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.post(
        url,
        auth=BITBUCKET_AUTH,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


def _del(endpoint: str) -> Any:
    return _request("DELETE", endpoint)


def _workspace() -> str:
    """Return the configured default workspace (may be empty)."""
    return BITBUCKET_WORKSPACE


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def _fmt_repo(r: dict) -> dict:
    return {
        "name": r.get("name"),
        "full_name": r.get("full_name"),
        "uuid": r.get("uuid"),
        "slug": r.get("slug"),
        "language": r.get("language"),
        "is_private": r.get("is_private"),
        "description": r.get("description"),
        "created_on": r.get("created_on"),
        "updated_on": r.get("updated_on"),
        "mainbranch": (r.get("mainbranch") or {}).get("name"),
        "links": {
            "html": ((r.get("links") or {}).get("html") or {}).get("href"),
        },
    }


def _fmt_commit(c: dict) -> dict:
    author = c.get("author") or {}
    user = author.get("user") or {}
    return {
        "hash": c.get("hash"),
        "message": (c.get("message") or "").strip(),
        "author": user.get("display_name") or author.get("raw") or c.get("author") or "unknown",
        "email": (user.get("email") or author.get("email") or ""),
        "date": c.get("date"),
    }


def _fmt_pr(pr: dict) -> dict:
    source = (pr.get("source") or {}) | {}
    destination = (pr.get("destination") or {}) | {}
    return {
        "id": pr.get("id"),
        "title": pr.get("title"),
        "description": pr.get("description"),
        "state": pr.get("state"),
        "created_on": pr.get("created_on"),
        "updated_on": pr.get("updated_on"),
        "author": ((pr.get("author") or {}).get("display_name") or ""),
        "source_branch": (source.get("branch") or {}).get("name"),
        "destination_branch": (destination.get("branch") or {}).get("name"),
        "links": {
            "html": ((pr.get("links") or {}).get("html") or {}).get("href"),
        },
    }
