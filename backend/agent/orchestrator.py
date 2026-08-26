"""
agent/orchestrator.py

Orchestrator Agent
==================
Implements the Observe → Think → Act loop.

Flow:
    User message
        │
        ▼
    ORCHESTRATOR LOOP (Observe → Think → Act)
        │
        ├── decides tool calls each turn
        │       │
        │       ▼
        │   TOOL CALLS (19 tools) ──► real ClickUp API / aggregators
        │
        └── replies back to user when done

The LLM (AWS Bedrock / Claude) is the brain.
Tool execution is deterministic Python code in tools/.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent.llm import get_llm
from tools import TOOL_MAP, TOOL_REGISTRY

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 12  # safety cap to prevent infinite loops

# ---------------------------------------------------------------------------
# System prompt — describes available tools to the LLM
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    tool_docs = "\n\n".join(
        f"### {t['name']}\n"
        f"Description: {t['description']}\n"
        f"Parameters: {json.dumps(t['params'], indent=2)}"
        for t in TOOL_REGISTRY
    )

    return f"""You are a ClickUp AI assistant with direct access to the ClickUp API.
You help the team leader manage tasks, track progress, and create tasks autonomously.

## Available Tools ({len(TOOL_REGISTRY)} total)

{tool_docs}

## How to Use Tools

To call a tool, respond with a JSON block (and NOTHING else in that turn):

```json
{{
  "tool": "<tool_name>",
  "args": {{
    "<param1>": "<value1>",
    "<param2>": "<value2>"
  }}
}}
```

After receiving a tool result you may call another tool or write your final answer.
When you have enough information to fully answer the user, write a plain text response
(no JSON block). That signals the end of the loop.

## Behaviour Rules
- Always resolve workspace hierarchy top-down: workspace → space → folder → list → task.
- When creating tasks, first call get_workspaces, then navigate to the correct list.
- When asked for a dashboard, call get_team_tasks → classify_tasks → build_dashboard → render_dashboard_text.
- Never guess IDs — always fetch them from the API first.
- Be concise and professional in final replies.
"""


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def _dispatch(tool_name: str, args: dict) -> Any:
    entry = TOOL_MAP.get(tool_name)
    if not entry:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        result = entry["fn"](**args)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_JSON_RE  = re.compile(r"^\s*(\{.*?\})\s*$", re.DOTALL)


def _extract_tool_call(text: str) -> dict | None:
    """
    Try to parse a tool call from the LLM response.
    Returns None if the response is a plain text (final) answer.
    """
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


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Stateful orchestrator.  One instance per conversation / session.

    Usage:
        orch = Orchestrator()
        reply = orch.run("Show me the dashboard for workspace 12345")
        print(reply)
    """

    def __init__(self) -> None:
        self.llm = get_llm()
        self.system = _build_system_prompt()
        self.history: list[dict[str, str]] = []
        self._tool_calls_log: list[dict] = []

    def run(self, user_message: str) -> str:
        """
        Run the Observe → Think → Act loop for a single user message.
        Returns the final assistant reply.
        """
        logger.info("User: %s", user_message)
        self.history.append({"role": "user", "content": user_message})

        for iteration in range(MAX_ITERATIONS):
            # ── THINK ──────────────────────────────────────────────────
            assistant_text = self.llm.chat(
                messages=self.history,
                system=self.system,
            )
            logger.debug("LLM [iter %d]: %s", iteration, assistant_text[:200])

            # ── ACT ────────────────────────────────────────────────────
            tool_call = _extract_tool_call(assistant_text)

            if tool_call is None:
                # No tool call → final answer
                self.history.append({"role": "assistant", "content": assistant_text})
                logger.info("Final answer after %d iteration(s)", iteration + 1)
                return assistant_text

            # Execute tool
            tool_name = tool_call["tool"]
            tool_args  = tool_call.get("args", {})
            logger.info("Tool call [iter %d]: %s(%s)", iteration, tool_name, tool_args)

            result = _dispatch(tool_name, tool_args)
            result_text = json.dumps(result, default=str, indent=2)

            self._tool_calls_log.append(
                {"iteration": iteration, "tool": tool_name, "args": tool_args, "result_preview": result_text[:300]}
            )

            # Append assistant tool-call message + tool result as next user turn
            self.history.append({"role": "assistant", "content": assistant_text})
            self.history.append(
                {
                    "role": "user",
                    "content": f"[TOOL RESULT: {tool_name}]\n{result_text}",
                }
            )

        # Fallback if max iterations hit
        fallback = "I reached the maximum number of steps without completing your request. Please try rephrasing."
        self.history.append({"role": "assistant", "content": fallback})
        return fallback

    def reset(self) -> None:
        """Clear conversation history (start fresh)."""
        self.history = []
        self._tool_calls_log = []

    @property
    def tool_calls_log(self) -> list[dict]:
        return self._tool_calls_log
