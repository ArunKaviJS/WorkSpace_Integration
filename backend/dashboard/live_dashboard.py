"""
dashboard/live_dashboard.py
Fetches workspace data and renders the team-leader dashboard to stdout.
Run:  python dashboard/live_dashboard.py
"""
from __future__ import annotations

import json
import logging
import sys

# Ensure project root on path when run directly
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.workspace_tools import get_workspaces, get_spaces, get_folders, get_lists, get_folderless_lists
from tools.task_tools import get_tasks, classify_tasks
from tools.dashboard_tools import build_dashboard, render_dashboard_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def gather_all_tasks() -> list[dict]:
    """Walk the full hierarchy and collect every task."""
    all_tasks: list[dict] = []

    workspaces = get_workspaces()
    for ws in workspaces:
        logger.info("Workspace: %s (%s)", ws["name"], ws["id"])
        spaces = get_spaces(ws["id"])

        for space in spaces:
            logger.info("  Space: %s (%s)", space["name"], space["id"])

            # Folderless lists
            for lst in get_folderless_lists(space["id"]):
                logger.info("    [folderless] List: %s (%s)", lst["name"], lst["id"])
                tasks = get_tasks(lst["id"])
                all_tasks.extend(tasks)

            # Folders → lists
            for folder in get_folders(space["id"]):
                logger.info("    Folder: %s (%s)", folder["name"], folder["id"])
                for lst in get_lists(folder["id"]):
                    logger.info("      List: %s (%s)", lst["name"], lst["id"])
                    tasks = get_tasks(lst["id"])
                    all_tasks.extend(tasks)

    return all_tasks


def main() -> None:
    print("Fetching ClickUp data …")
    tasks = gather_all_tasks()
    classified = classify_tasks(tasks)
    dashboard = build_dashboard(classified)
    print(render_dashboard_text(dashboard))

    # Also write JSON snapshot
    out_path = os.path.join(os.path.dirname(__file__), "dashboard_snapshot.json")
    with open(out_path, "w") as fh:
        json.dump(dashboard, fh, indent=2, default=str)
    print(f"\nJSON snapshot written to {out_path}")


if __name__ == "__main__":
    main()
