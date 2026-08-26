"""
tools/dashboard_tools.py
Generates the unified team-leader dashboard summary from raw task data.
No API calls here — pure aggregation / formatting.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


def build_dashboard(classified: dict, member_map: dict[str, str] | None = None) -> dict:
    """
    TOOL: build_dashboard
    Build a structured dashboard dict from classified task data.

    Parameters
    ----------
    classified  : dict returned by classify_tasks()
    member_map  : {user_id: username} for display purposes (optional)

    Returns a rich dict suitable for rendering or JSON export.
    """
    now = time.time()
    member_map = member_map or {}

    # Per-developer breakdown
    dev_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"completed": [], "pending": [], "overdue": [], "due_soon": []}
    )

    def _add(bucket: str, tasks: list[dict]) -> None:
        for t in tasks:
            for assignee in t.get("assignees") or ["unassigned"]:
                dev_stats[assignee][bucket].append(t["name"])

    _add("completed", classified.get("completed", []))
    _add("pending", classified.get("pending", []))
    _add("overdue", classified.get("overdue", []))
    _add("due_soon", classified.get("due_soon_5min", []))

    # Tasks due in the next 24 hours
    upcoming_24h = [
        dict(t)
        for t in classified.get("pending", [])
        if t.get("due_date_epoch") and 0 < (t["due_date_epoch"] - now) <= 86400
    ]
    for t in upcoming_24h:
        t["due_in_minutes"] = round((t["due_date_epoch"] - now) / 60, 1)
    upcoming_24h.sort(key=lambda x: x["due_date_epoch"])

    overdue_full = [dict(t) for t in classified.get("overdue", [])]
    for t in overdue_full:
        t["minutes_overdue"] = (
            round((now - t["due_date_epoch"]) / 60, 1) if t.get("due_date_epoch") else None
        )

    due_soon_full = [dict(t) for t in classified.get("due_soon_5min", [])]
    for t in due_soon_full:
        t["seconds_remaining"] = (
            round(t["due_date_epoch"] - now, 0) if t.get("due_date_epoch") else None
        )

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "summary": {
            "total": classified.get("total", 0),
            "completed": len(classified.get("completed", [])),
            "pending": len(classified.get("pending", [])),
            "overdue": len(classified.get("overdue", [])),
            "due_soon_5min": len(classified.get("due_soon_5min", [])),
            "upcoming_24h": len(upcoming_24h),
        },
        "per_developer": dict(dev_stats),
        "upcoming_24h": upcoming_24h,
        "overdue_tasks": overdue_full,
        "due_soon_5min": due_soon_full,
    }


def render_dashboard_text(dashboard: dict) -> str:
    """
    TOOL: render_dashboard_text
    Convert a dashboard dict to a human-readable text report.

    Parameters
    ----------
    dashboard : dict returned by build_dashboard()
    """
    s = dashboard["summary"]
    lines = [
        "=" * 60,
        f"  CLICKUP TEAM DASHBOARD  —  {dashboard['generated_at']}",
        "=" * 60,
        "",
        "SUMMARY",
        f"  Total tasks    : {s['total']}",
        f"  Completed      : {s['completed']}",
        f"  Pending        : {s['pending']}",
        f"  Overdue        : {s['overdue']}",
        f"  Due in 5 min   : {s['due_soon_5min']}",
        f"  Due in 24 h    : {s['upcoming_24h']}",
        "",
    ]

    if dashboard["due_soon_5min"]:
        lines.append("⚠️  DUE IN 5 MINUTES")
        for t in dashboard["due_soon_5min"]:
            lines.append(
                f"  [{t['id']}] {t['name']} — {t['assignees']} — "
                f"{t['seconds_remaining']}s remaining"
            )
        lines.append("")

    if dashboard["overdue_tasks"]:
        lines.append("🚨  OVERDUE TASKS")
        for t in dashboard["overdue_tasks"]:
            lines.append(f"  [{t['id']}] {t['name']} — {t['assignees']}")
        lines.append("")

    if dashboard["upcoming_24h"]:
        lines.append("⏳  DUE NEXT 24 HOURS")
        for t in dashboard["upcoming_24h"]:
            lines.append(
                f"  [{t['id']}] {t['name']} — {t['assignees']} — "
                f"in {t['due_in_minutes']} min"
            )
        lines.append("")

    lines.append("👥  PER-DEVELOPER BREAKDOWN")
    for dev, stat in dashboard["per_developer"].items():
        lines.append(f"\n  {dev}:")
        lines.append(f"    ✅ Completed : {len(stat['completed'])}")
        lines.append(f"    ⏳ Pending   : {len(stat['pending'])}")
        lines.append(f"    🚨 Overdue   : {len(stat['overdue'])}")
        if stat["due_soon"]:
            lines.append(f"    ⚠️  Due soon  : {stat['due_soon']}")

    lines += ["", "=" * 60]
    return "\n".join(lines)
