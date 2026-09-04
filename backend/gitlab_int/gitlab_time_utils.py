"""
gitlab_int/gitlab_time_utils.py
Time/date utilities for the GitLab context — commit timestamps and MR age —
following the same pattern as tools/time_utils.py and bitbucket_time_utils.py.

GitLab returns ISO-8601 timestamps (e.g. "2026-08-27T10:15:30.000Z" or
"2026-08-27T10:15:30+00:00"). These helpers parse them into a common
epoch/readable form and compute human-friendly durations ("2h ago", "3d waiting").
"""
from __future__ import annotations

from datetime import datetime, timezone

from tools.time_utils import IST


def parse_iso(iso: str) -> datetime | None:
    """Parse a GitLab ISO-8601 timestamp into an aware datetime (UTC if naive)."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def iso_to_epoch_sec(iso: str) -> int | None:
    dt = parse_iso(iso)
    return int(dt.timestamp()) if dt else None


def iso_to_display(iso: str) -> str:
    dt = parse_iso(iso)
    if not dt:
        return ""
    return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")


def _describe_duration(seconds: float) -> str:
    neg = seconds < 0
    s = abs(int(seconds))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d > 0:
        text = f"{d}d {h}h"
    elif h > 0:
        text = f"{h}h {m}m"
    else:
        text = f"{m}m"
    return f"-{text}" if neg else text


def age_from_iso(iso: str, now: datetime | None = None) -> str:
    """How long ago an ISO timestamp was, e.g. '2d 3h' / '0m'."""
    dt = parse_iso(iso)
    if not dt:
        return "unknown"
    now = now or datetime.now(timezone.utc)
    return _describe_duration((now - dt).total_seconds())


def mr_wait_epoch_secs(created_iso: str, now: datetime | None = None) -> int | None:
    """Whole seconds a merge request has been waiting since it was created."""
    dt = parse_iso(created_iso)
    if not dt:
        return None
    now = now or datetime.now(timezone.utc)
    return int((now - dt).total_seconds())


def format_commits(commits: list[dict]) -> list[dict]:
    """Augment dashboard commit dicts with epoch + human-friendly timestamp labels."""
    for c in commits:
        iso = c.get("date") or c.get("created_at") or c.get("committed_date")
        c["epoch_sec"] = iso_to_epoch_sec(iso)
        c["date_display"] = iso_to_display(iso) if iso else ""
        c["date_age"] = age_from_iso(iso) if iso else "unknown"
    return commits
