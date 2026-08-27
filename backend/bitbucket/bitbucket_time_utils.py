"""
bitbucket/bitbucket_time_utils.py
Time/date utilities specific to the Bitbucket context — PR age, commit
timestamps, branch activity — following the same pattern as tools/time_utils.py.

Bitbucket returns ISO-8601 timestamps (e.g. "2026-08-27T10:15:30+00:00").
These helpers parse them into a common epoch/readable form and compute
human-friendly durations ("2h ago", "3d waiting").
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from tools.time_utils import IST

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def parse_iso(iso: str) -> datetime | None:
    """Parse a Bitbucket ISO-8601 timestamp into an aware datetime.

    Bitbucket usually appends timezone info ("+00:00"). When it is missing we
    assume UTC so that duration math stays consistent.
    """
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def iso_to_epoch_sec(iso: str) -> int | None:
    """Convert an ISO-8601 timestamp to Unix epoch seconds (or None)."""
    dt = parse_iso(iso)
    return int(dt.timestamp()) if dt else None


def iso_to_display(iso: str) -> str:
    """Human-readable display version of a Bitbucket ISO timestamp (IST)."""
    dt = parse_iso(iso)
    if not dt:
        return ""
    return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")


# ---------------------------------------------------------------------------
# Duration helpers
# ---------------------------------------------------------------------------


def _describe_duration(seconds: int) -> str:
    """Collapse a number of seconds into a compact '1d 2h' style string."""
    neg = seconds < 0
    s = abs(int(seconds))
    d = s // 86400
    s -= d * 86400
    h = s // 3600
    s -= h * 3600
    m = s // 60

    if d > 0:
        text = f"{d}d {h}h"
    elif h > 0:
        text = f"{h}h {m}m"
    else:
        text = f"{m}m"
    return f"-{text}" if neg else text


def age_from_iso(iso: str, now: datetime | None = None) -> str:
    """Return how long ago an ISO timestamp was, e.g. '2d 3h' / 'now'.

    Used for PR waiting time and branch activity.
    """
    dt = parse_iso(iso)
    if not dt:
        return "unknown"
    if now is None:
        now = datetime.now(timezone.utc)
    delta = now - dt
    return _describe_duration(delta.total_seconds())


def commit_timestamp_epoch(commit: dict) -> int | None:
    """Extract the epoch (seconds) of a commit from a raw Bitbucket commit.

    Bitbucket commits carry `date` on the top-level object (API v2), falling
    back to `author.date` inside the author object for webhook payloads.
    """
    iso = commit.get("date") or (commit.get("author") or {}).get("date")
    return iso_to_epoch_sec(iso)


def pr_wait_epoch_secs(pr_created_iso: str, now: datetime | None = None) -> int | None:
    """Whole seconds a PR has been waiting since it was created."""
    dt = parse_iso(pr_created_iso)
    if not dt:
        return None
    if now is None:
        now = datetime.now(timezone.utc)
    return int((now - dt).total_seconds())


def format_branch_activity(branches: list[dict]) -> list[dict]:
    """Augment raw branch objects with human-friendly updated/created labels."""
    for b in branches:
        updated = b.get("updated_on") or b.get("date")
        b["updated_display"] = iso_to_display(updated) if updated else ""
        b["updated_age"] = age_from_iso(updated) if updated else "unknown"
    return branches


def format_commits(commits: list[dict]) -> list[dict]:
    """Augment raw commit objects with epoch + human-friendly timestamp labels."""
    for c in commits:
        c["epoch_sec"] = commit_timestamp_epoch(c)
        c["date_display"] = iso_to_display(c.get("date")) if c.get("date") else ""
        c["date_age"] = age_from_iso(c.get("date")) if c.get("date") else "unknown"
    return commits
