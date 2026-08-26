"""
tools/time_utils.py
Resolves relative date words ("today", "tomorrow", "next monday" etc.)
into concrete IST dates BEFORE the message reaches the LLM.

This is deterministic code-level resolution — far more reliable than letting
the LLM do date arithmetic. Integrated into the orchestrator so every user
message and the system prompt both carry resolved dates.
"""
import re
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]
_WD_ALT = "|".join(WEEKDAYS)

_RELATIVE_RE = re.compile(
    rf"\b(day after tomorrow|tomorrow|today|tonight|this weekend|next week|"
    rf"this ({_WD_ALT})|next ({_WD_ALT})|in a week|in (\d+) days?|"
    rf"(\d+) days? (?:from now|later))\b",
    re.IGNORECASE,
)


def ist_now() -> str:
    """Return the current IST date/time as a readable string.
    Injected into the system prompt so the LLM never misreads the clock."""
    now = datetime.now(IST)
    return now.strftime(
        "Today is %A, %d %B %Y. Current time is %H:%M (IST, UTC+5:30)."
    )


def _shift_weekday(now: datetime, weekday: str, following: bool = False) -> datetime.date:
    """Next occurrence of a weekday from 'now'.  If *following*, always skip
    to the next week (so 'next monday' on a monday means +7 days, not today)."""
    target = WEEKDAYS.index(weekday.lower())
    delta = (target - now.weekday()) % 7
    if delta == 0 and following:
        delta = 7
    return now.date() + timedelta(days=delta)


def resolve_relative_dates(text: str, now: datetime | None = None) -> str:
    """Replace relative date words with concrete IST dates.

    Example
    -------
    "Create a task tomorrow"  →  "Create a task tomorrow (Wednesday, 27 August 2026)"
    """
    if not text:
        return text
    if now is None:
        now = datetime.now(IST)

    def _repl(m: re.Match) -> str:
        token = m.group(0).strip().lower()
        today = now.date()

        if token == "day after tomorrow":
            d = today + timedelta(days=2)
            return f"day after tomorrow ({d.strftime('%A, %d %B %Y')})"
        if token == "tomorrow":
            d = today + timedelta(days=1)
            return f"tomorrow ({d.strftime('%A, %d %B %Y')})"
        if token == "today":
            return f"today ({today.strftime('%A, %d %B %Y')})"
        if token == "tonight":
            return f"tonight ({today.strftime('%A, %d %B %Y')} evening)"
        if token == "this weekend":
            d = _shift_weekday(now, "saturday")
            return f"this weekend ({d.strftime('%A, %d %B %Y')})"
        if token == "next week":
            d = today + timedelta(days=7)
            return f"next week ({d.strftime('%A, %d %B %Y')})"
        if token == "in a week":
            d = today + timedelta(days=7)
            return f"in a week ({d.strftime('%A, %d %B %Y')})"
        if token.startswith("this "):
            d = _shift_weekday(now, token.split(" ", 1)[1])
            return f"{token} ({d.strftime('%A, %d %B %Y')})"
        if token.startswith("next "):
            d = _shift_weekday(now, token.split(" ", 1)[1], following=True)
            return f"{token} ({d.strftime('%A, %d %B %Y')})"
        mnum = re.match(r"in (\d+) days?", token) or re.match(
            r"(\d+) days? (?:from now|later)", token
        )
        if mnum:
            d = today + timedelta(days=int(mnum.group(1)))
            return f"in {mnum.group(1)} days ({d.strftime('%A, %d %B %Y')})"
        return m.group(0)

    return _RELATIVE_RE.sub(_repl, text)


def compute_due_epoch_ms(text: str, now: datetime | None = None) -> int | None:
    """If the user says 'tomorrow' or 'next friday' as the ONLY due-date
    instruction, return the epoch-ms at 23:59 IST that day.

    Returns None when the text doesn't contain a clear due-date word,
    letting the LLM handle it via tool args instead.
    """
    if now is None:
        now = datetime.now(IST)

    # Check for common due-date phrases at the end of a sentence
    patterns = [
        (r"due\s+(?:on\s+)?(?:this\s+)?(tomorrow|today|next\s+\w+)", 1),
        (r"(?:set\s+)?(?:due\s+date|deadline)\s+(?:to\s+)?(?:this\s+)?(tomorrow|today|next\s+\w+)", 1),
        (r"^\s*(?:due\s+)?(?:on\s+)?(tomorrow|today|next\s+\w+)\s*\.?\s*$", 1),
    ]
    token = None
    for pat, grp in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            token = m.group(grp).strip().lower()
            break

    if not token:
        return None

    if token == "today":
        d = now.date()
    elif token == "tomorrow":
        d = now.date() + timedelta(days=1)
    elif token.startswith("next "):
        wk = token.split(" ", 1)[1]
        d = _shift_weekday(now, wk, following=True)
    else:
        return None

    # End-of-day: 23:59:59 IST
    from datetime import time as t
    dt = datetime.combine(d, t(23, 59, 59), tzinfo=IST)
    return int(dt.timestamp() * 1000)
