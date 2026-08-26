"""
main.py
Interactive CLI for the ClickUp AI Agent.

Usage:
    python main.py

Examples of what you can type:
    "Show me the dashboard"
    "What tasks are overdue?"
    "Create a task called 'Fix login bug' in list 12345 and assign to user 67890"
    "What workspaces do I have?"
    "Show all pending tasks across the workspace"
"""
from __future__ import annotations

import logging
import sys

from agent.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          ClickUp AI Agent  —  powered by AWS Bedrock         ║
║  Type your request. 'exit' to quit. 'reset' to clear history ║
╚══════════════════════════════════════════════════════════════╝
"""


def main() -> None:
    print(BANNER)
    agent = Orchestrator()

    while True:
        try:
            user_input = input("\n🤖  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            sys.exit(0)

        if not user_input:
            continue
        if user_input.lower() == "exit":
            print("Goodbye!")
            sys.exit(0)
        if user_input.lower() == "reset":
            agent.reset()
            print("✅  Conversation history cleared.")
            continue

        print()
        reply = agent.run(user_input)
        print(f"🟢  Agent:\n{reply}")

        if agent.tool_calls_log:
            print(f"\n   [Used {len(agent.tool_calls_log)} tool call(s) this session]")


if __name__ == "__main__":
    main()
