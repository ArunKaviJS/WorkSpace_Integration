"""
gitlab_int/__init__.py
GitLab integration — a completely separate integration from ClickUp and Bitbucket.

Uses the official `python-gitlab` SDK (personal-access-token auth) instead of a
hand-rolled REST client. Contains its own tools, prompts, time utilities, chat
agent, a dedicated code-review agent, and API routes so the GitLab AI agent can
be reasoned about and extended independently.

The package is named `gitlab_int` (not `gitlab`) so it never shadows the
`python-gitlab` top-level `import gitlab`.
"""
from __future__ import annotations

from gitlab_int.gitlab_tools import GITLAB_TOOL_MAP, GITLAB_TOOL_REGISTRY

__all__ = ["GITLAB_TOOL_MAP", "GITLAB_TOOL_REGISTRY"]
