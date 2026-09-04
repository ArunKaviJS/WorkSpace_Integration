"""
gitlab_int/gitlab_agent.py
GitLab AI Agent — a separate agent from the ClickUp and Bitbucket agents.

It reuses the same Observe → Think → Act loop pattern (see
agent/orchestrator.py and bitbucket/bitbucket_agent.py) but keeps its own
conversation history, tool-call log, tool registry and system prompt. The
centralised Bedrock LLM singleton (agent.llm.get_llm) is shared — no new LLM
client is created.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent.llm import get_llm
from gitlab_int.gitlab_client import GitLabError
from gitlab_int.gitlab_prompts import build_gitlab_system_prompt
from gitlab_int.gitlab_tools import GITLAB_TOOL_MAP
from tools.time_utils import resolve_relative_dates

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 12  # safety cap — matches agent/orchestrator.py

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"^\s*(\{.*?\})\s*$", re.DOTALL)


def _dispatch(tool_name: str, args: dict) -> Any:
    entry = GITLAB_TOOL_MAP.get(tool_name)
    if not entry:
        return {"error": True, "message": f"Unknown tool: {tool_name}", "status_code": 0}
    try:
        return entry["fn"](**args)
    except GitLabError as exc:
        logger.error("GitLab tool %s failed: %s", tool_name, exc)
        return {"error": True, "message": str(exc), "status_code": exc.status_code}
    except TypeError as exc:  # bad/missing args from the LLM
        logger.error("GitLab tool %s bad args %s: %s", tool_name, args, exc)
        return {"error": True, "message": f"Bad arguments for {tool_name}: {exc}", "status_code": 0}
    except Exception as exc:  # noqa: BLE001
        logger.error("GitLab tool %s failed: %s", tool_name, exc, exc_info=True)
        return {"error": True, "message": str(exc), "status_code": 0}


def _extract_tool_call(text: str) -> dict | None:
    """Parse a tool call from the LLM response. None = final answer."""
    for pattern in (_JSON_BLOCK_RE, _BARE_JSON_RE):
        m = pattern.search(text)
        if m:
            try:
                obj = json.loads(m.group(1))
                if "tool" in obj:
                    return obj
            except json.JSONDecodeError:
                pass
    return None


class GitLabAgent:
    """Stateful GitLab agent. One instance per conversation/session."""

    def __init__(self) -> None:
        self.llm = get_llm()  # shared centralised LLM singleton
        self.system = build_gitlab_system_prompt()
        self.history: list[dict[str, str]] = []
        self._tool_calls_log: list[dict] = []

    def run(self, user_message: str) -> str:
        """Run the Observe → Think → Act loop for a single user message."""
        if user_message.strip().lower() == "reset":
            self.reset()
            return "Conversation cleared. What can I do for you?"

        user_message = resolve_relative_dates(user_message)
        logger.info("GitLab User: %s", user_message)
        self.history.append({"role": "user", "content": user_message})

        for iteration in range(MAX_ITERATIONS):
            assistant_text = self.llm.chat(messages=self.history, system=self.system)
            tool_call = _extract_tool_call(assistant_text)

            if tool_call is None:
                self.history.append({"role": "assistant", "content": assistant_text})
                logger.info("Final answer after %d iteration(s)", iteration + 1)
                return assistant_text

            tool_name = tool_call["tool"]
            tool_args = tool_call.get("args", {})
            logger.info("Tool call [iter %d]: %s(%s)", iteration, tool_name, tool_args)

            result = _dispatch(tool_name, tool_args)
            result_text = json.dumps(result, default=str, indent=2)

            self._tool_calls_log.append(
                {
                    "iteration": iteration,
                    "tool": tool_name,
                    "args": tool_args,
                    "result_preview": result_text[:300],
                }
            )

            self.history.append({"role": "assistant", "content": assistant_text})
            self.history.append(
                {"role": "user", "content": f"[TOOL RESULT: {tool_name}]\n{result_text}"}
            )

        fallback = (
            "I reached the maximum number of steps without completing your request. "
            "Please try rephrasing."
        )
        self.history.append({"role": "assistant", "content": fallback})
        return fallback

    def reset(self) -> None:
        self.history = []
        self._tool_calls_log = []

    @property
    def tool_calls_log(self) -> list[dict]:
        return self._tool_calls_log
