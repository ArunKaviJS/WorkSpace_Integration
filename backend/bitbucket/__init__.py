"""
bitbucket/__init__.py
Bitbucket module — a completely separate integration from ClickUp.

Contains its own tools, prompts, time utilities, agent and API routes so that
the Bitbucket AI agent can be reasoned about and extended independently.
"""
from __future__ import annotations

# Import the tool registry so the agent can dispatch Bitbucket tools.
from bitbucket.bitbucket_tools import BITBUCKET_TOOL_MAP, BITBUCKET_TOOL_REGISTRY

__all__ = ["BITBUCKET_TOOL_MAP", "BITBUCKET_TOOL_REGISTRY"]
