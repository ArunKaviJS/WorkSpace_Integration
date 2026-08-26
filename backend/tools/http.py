"""
tools/http.py
Shared thin HTTP helper for all ClickUp tool modules.
"""
from __future__ import annotations

from typing import Any

import requests

from config.settings import CLICKUP_BASE_URL, CLICKUP_HEADERS

V3_URL = "https://api.clickup.com/api/v3"


def request(
    method: str,
    endpoint: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    files: dict | None = None,
    base: str | None = None,
) -> Any:
    url = f"{base or CLICKUP_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.request(
        method,
        url,
        headers=CLICKUP_HEADERS,
        params=params or {},
        json=json_body,
        files=files,
        timeout=30,
    )
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


def get(endpoint: str, params: dict | None = None, *, base: str | None = None) -> Any:
    return request("GET", endpoint, params=params, base=base)


def post(endpoint: str, payload: dict | None = None, *, base: str | None = None) -> Any:
    return request("POST", endpoint, json_body=payload, base=base)


def put(endpoint: str, payload: dict | None = None, *, base: str | None = None) -> Any:
    return request("PUT", endpoint, json_body=payload, base=base)


def patch(endpoint: str, payload: dict | None = None, *, base: str | None = None) -> Any:
    return request("PATCH", endpoint, json_body=payload, base=base)


def delete(endpoint: str, params: dict | None = None) -> Any:
    return request("DELETE", endpoint, params=params)
