"""
gitlab_int/gitlab_client.py
Shared python-gitlab client + helpers for every GitLab tool module.

Auth strategy (the "safest version that works on all python-gitlab versions"):

    gl = gitlab.Gitlab(url=GITLAB_URL, private_token=GITLAB_TOKEN)
    gl.auth()          # sets gl.user automatically
    me = gl.user       # always works, no method call needed

The concrete tool functions live in sibling modules (project_tools, mr_tools,
branch_tools, pipeline_tools, review_agent) which import the helpers here.
Keeping the client + error shaping in one place avoids duplicating auth logic.
"""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable

import gitlab
import gitlab.exceptions
import requests.exceptions

from config.settings import GITLAB_TOKEN, GITLAB_URL

logger = logging.getLogger(__name__)

# How much diff/patch text we ever hand to the LLM in one shot.
MAX_DIFF_CHARS = 16000


class GitLabError(Exception):
    """Error from the GitLab API carrying a status code.

    Mirrors ``bitbucket.bitbucket_http.BitbucketError`` so the agent dispatcher
    can emit a consistent ``{"error": true, "message": ..., "status_code": ...}``
    JSON response regardless of which integration produced it.
    """

    def __init__(self, status_code: int | None, message: str = "", *args: Any) -> None:
        self.status_code = int(status_code or 0)
        self.message = message or f"GitLab API error (HTTP {self.status_code})"
        super().__init__(self.message, *args)


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_gl: gitlab.Gitlab | None = None


def get_gl() -> gitlab.Gitlab:
    """Lazily create (and reuse) a single authenticated python-gitlab client."""
    global _gl
    if _gl is not None:
        return _gl

    if not GITLAB_URL or not GITLAB_TOKEN:
        raise GitLabError(
            0,
            "GITLAB_URL / GITLAB_TOKEN are not configured. Add them to the "
            "backend environment before using the GitLab tab.",
        )

    try:
        client = gitlab.Gitlab(url=GITLAB_URL, private_token=GITLAB_TOKEN)
        client.auth()  # this sets client.user automatically
    except gitlab.exceptions.GitlabAuthenticationError as exc:
        raise GitLabError(401, f"GitLab authentication failed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - surface any connection failure cleanly
        raise GitLabError(0, f"Could not connect to GitLab at {GITLAB_URL}: {exc}") from exc

    _gl = client
    logger.info(
        "python-gitlab ready — url=%s user=%s",
        GITLAB_URL,
        getattr(client.user, "username", "?"),
    )
    return _gl


def current_user() -> dict:
    """Return the authenticated user (``gl.user`` — always populated by auth())."""
    u = get_gl().user
    return {
        "id": getattr(u, "id", None),
        "username": getattr(u, "username", None),
        "name": getattr(u, "name", None),
        "email": getattr(u, "email", ""),
        "web_url": getattr(u, "web_url", ""),
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def translate_gitlab_error(exc: Exception, context: str = "") -> GitLabError:
    """Turn a python-gitlab / requests exception into a plain-language GitLabError.

    Permission rejections (401/403) become an explicit "you don't have access"
    message instead of a raw traceback; network failures say so clearly.
    """
    if isinstance(exc, GitLabError):
        return exc

    where = f" for {context}" if context else ""

    if isinstance(exc, requests.exceptions.RequestException):
        return GitLabError(
            0,
            f"Could not reach GitLab at {GITLAB_URL}{where} — network, proxy, VPN, "
            f"TLS, or wrong GITLAB_URL. ({exc})",
        )

    code = int(getattr(exc, "response_code", 0) or 0)
    raw = str(exc)

    if code == 401:
        msg = (
            f"GitLab rejected the token (401){where}: it is invalid, expired, or "
            f"missing the required 'api' scope."
        )
    elif code == 403:
        msg = (
            f"You don't have permission for this action in GitLab (403){where}. "
            f"The token's user needs a higher role (Developer / Maintainer / Owner) "
            f"on the target project or group — or project-creation rights in that "
            f"namespace — and the token must have the 'api' scope."
        )
    elif code == 404:
        msg = f"Not found (404){where} — or the token's user has no access to it."
    elif code == 409:
        msg = f"Conflict (409){where} — the resource may already exist."
    elif code == 400:
        msg = f"GitLab rejected the request (400){where}: {raw}"
    else:
        msg = raw or f"GitLab API error{where}"

    return GitLabError(code, msg)


def gl_call(fn: Callable) -> Callable:
    """Decorator: translate python-gitlab / network exceptions into GitLabError."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except GitLabError:
            raise
        except (gitlab.exceptions.GitlabError, requests.exceptions.RequestException) as exc:
            raise translate_gitlab_error(exc) from exc

    return wrapper


def get_project(project_id: str | int) -> Any:
    """Resolve a project by numeric id OR ``namespace/path`` string."""
    try:
        return get_gl().projects.get(project_id)
    except (gitlab.exceptions.GitlabError, requests.exceptions.RequestException) as exc:
        raise translate_gitlab_error(exc, f"project '{project_id}'") from exc


def list_bounded(manager: Any, *, limit: int = 100, **kwargs: Any) -> list:
    """List the first ``limit`` items from a python-gitlab manager.

    Uses a single page request (``per_page``) so it stays fast and works across
    every python-gitlab version without the ``all=`` / ``get_all=`` / ``iterator=``
    keyword churn.
    """
    per_page = max(1, min(int(limit), 100))
    try:
        return list(manager.list(per_page=per_page, page=1, **kwargs))
    except (gitlab.exceptions.GitlabError, requests.exceptions.RequestException) as exc:
        raise translate_gitlab_error(exc) from exc


def list_all(manager: Any, *, cap: int = 300, **kwargs: Any) -> list:
    """List up to ``cap`` items, paging if the SDK supports it."""
    try:
        try:
            items = list(manager.list(iterator=True, **kwargs))
        except TypeError:
            items = manager.list(all=True, **kwargs)
    except (gitlab.exceptions.GitlabError, requests.exceptions.RequestException) as exc:
        raise translate_gitlab_error(exc) from exc
    return list(items)[:cap]


def clip_text(text: str, limit: int = MAX_DIFF_CHARS) -> str:
    """Truncate long diff/patch text with a marker so the LLM context stays sane."""
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n… [truncated {len(text) - limit} more characters]"
