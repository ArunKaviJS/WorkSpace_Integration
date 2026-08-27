"""
bitbucket/bitbucket_prompts.py
All system and task prompts for the Bitbucket agent — kept fully separate from
the ClickUp prompts (which live inline in agent/orchestrator.py).

The system prompt is generated from the Bitbucket tool registry so the LLM
always knows the exact set of tools available, mirroring the ClickUp pattern.
"""
from __future__ import annotations

import json

from bitbucket.bitbucket_tools import BITBUCKET_TOOL_REGISTRY
from bitbucket.bitbucket_time_utils import (
    age_from_iso,
    iso_to_epoch_sec,
    pr_wait_epoch_secs,
)
from tools.time_utils import ist_now


def build_bitbucket_system_prompt() -> str:
    """Build the system prompt that describes the Bitbucket tools to the LLM."""
    tool_docs = "\n\n".join(
        f"### {t['name']}\n"
        f"Description: {t['description']}\n"
        f"Parameters: {json.dumps(t['params'], indent=2)}"
        for t in BITBUCKET_TOOL_REGISTRY
    )

    return f"""You are a Bitbucket AI assistant with direct access to the Bitbucket API.
You help the team lead manage repositories, pull requests, branches and commits.

## Available Tools ({len(BITBUCKET_TOOL_REGISTRY)} total)

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
- {ist_now()}
- Human-gated tools (approve_pr, decline_pr, merge_pr, delete_repo,
  set_branch_permission) REQUIRE confirmed=True to actually execute.
  If the user asked for one of these, first ask them to confirm, then call the
  tool with confirmed=True. NEVER pass confirmed=True on your own.
- The workspace defaults to the configured BITBUCKET_WORKSPACE. Only pass an
  explicit workspace when the user names a different one.
- Never guess repo slugs, PR IDs or commit SHAs — fetch them first with
  get_pending_prs / pull_repo_info / get_latest_commits before acting on them.
- To review a PR: pull its diff (get_pr_diff), then post_pr_comment with your
  feedback. Do not approve/decline without first confirming the user.
- Be concise and professional in final replies.
"""


def summarize_pending_pr(pr: dict) -> str:
    """Render a short human sentence for a pending PR (used by the dashboard)."""
    wait = pr_wait_epoch_secs(pr.get("created_on", ""))
    if wait is None:
        how_long = "unknown time"
    else:
        how_long = age_from_iso(pr.get("created_on", ""))
    return (
        f"[{pr.get('repo')}] #{pr.get('id')} — \"{pr.get('title')}\" "
        f"by {pr.get('author')} · waiting {how_long} · "
        f"{pr.get('source_branch')} → {pr.get('destination_branch')}"
    )


def summarize_commit(commit: dict) -> str:
    """Render a short human sentence for a commit."""
    return (
        f"[{commit.get('repo')}] {commit.get('author')} · {commit.get('date_display', '')} · "
        f"{commit.get('message')} ({commit.get('hash', '')[:8]})"
    )
