"""
bitbucket/live_dashboard.py
Standalone Bitbucket dashboard (no AI/LLM involved) — mirrors the ClickUp
backend/dashboard/live_dashboard.py pattern, but for Bitbucket.

It walks the configured workspace, pulls repository data, latest commits and
open pull requests through the Bitbucket tool layer, then prints a readable
report and writes a JSON snapshot.

Run (from backend/):
    python bitbucket/live_dashboard.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

# Ensure project root on path when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bitbucket.bitbucket_time_utils import age_from_iso, format_commits
from bitbucket.bitbucket_tools import get_latest_commits, get_pending_prs, list_repos

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def gather_dashboard() -> dict:
    """Collect repos, latest commits and pending PRs across the workspace."""
    repos = list_repos()
    logger.info("Repositories: %d", len(repos))
    commits = format_commits(get_latest_commits(limit=10))
    pending_prs = get_pending_prs()
    return {
        "repos": repos,
        "commits": commits,
        "pending_prs": pending_prs,
        "summary": {
            "total_repos": len(repos),
            "open_prs": len(pending_prs),
            "recent_commits": len(commits),
        },
    }


def _waiting_label(pr: dict) -> str:
    return age_from_iso(pr.get("created_on", "")) if pr.get("created_on") else "unknown"


def render_dashboard(dash: dict) -> str:
    """Format the gathered dashboard dict into a human-readable report."""
    s = dash["summary"]
    lines = [
        "=" * 60,
        "  BITBUCKET WORKSPACE DASHBOARD",
        "=" * 60,
        "",
        "SUMMARY",
        f"  Repositories    : {s['total_repos']}",
        f"  Open pull reqs  : {s['open_prs']}",
        f"  Recent commits  : {s['recent_commits']}",
        "",
    ]

    if dash["pending_prs"]:
        lines.append("⏳  OPEN PULL REQUESTS")
        for pr in dash["pending_prs"]:
            lines.append(
                f"  [{pr['repo']}] #{pr['id']} \"{pr['title']}\" — {pr['author']} "
                f"— waiting {_waiting_label(pr)} — "
                f"{pr['source_branch']} → {pr['destination_branch']}"
            )
        lines.append("")

    if dash["commits"]:
        lines.append("🚀  LATEST COMMITS")
        for c in dash["commits"]:
            lines.append(
                f"  [{c['repo']}] {c['author']} · {c.get('date_display', '')} · "
                f"{c['message']} ({c['hash'][:8]})"
            )
        lines.append("")

    lines += ["", "=" * 60]
    return "\n".join(lines)


def main() -> None:
    print("Fetching Bitbucket data …")
    dash = gather_dashboard()
    print(render_dashboard(dash))

    out_path = os.path.join(os.path.dirname(__file__), "bitbucket_dashboard_snapshot.json")
    with open(out_path, "w") as fh:
        json.dump(dash, fh, indent=2, default=str)
    print(f"\nJSON snapshot written to {out_path}")


if __name__ == "__main__":
    main()
