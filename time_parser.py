"""
Time parser for scheduling emails.
Supports ISO-8601, human-friendly expressions ('in 15 minutes', 'tomorrow at 9am'),
and relative time offsets.
"""

import re
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateutil_parser
from dateutil.tz import gettz
from typing import Tuple
from config import Config, logger


def get_default_tz():
    """Gets the configured timezone or local system timezone."""
    if Config.TIMEZONE:
        tz = gettz(Config.TIMEZONE)
        if tz:
            return tz
    return datetime.now().astimezone().tzinfo or timezone.utc


def parse_scheduled_time(time_str: str) -> Tuple[datetime, str]:
    """
    Parses a time string into a timezone-aware datetime object.
    Returns (parsed_datetime, explanation_string).
    
    Supports:
    - 'in X seconds/minutes/hours/days' (e.g., 'in 15 minutes', 'in 2 hours')
    - '+Xm', '+Xh', '+Xd'
    - 'today at HH:MM', 'tomorrow at HH:MM' (with optional AM/PM)
    - ISO 8601 strings and standard date formats ('2026-10-21 16:30:00', '2026-10-22T09:00:00Z')
    """
    raw_str = time_str.strip()
    tz = get_default_tz()
    now = datetime.now(tz)

    # 1. Check relative 'in X ...' pattern
    # e.g., 'in 10 minutes', 'in 2 hrs', 'in 1 day', 'in 45 seconds'
    rel_match = re.match(
        r"^(?:in|\+)\s*(\d+(?:\.\d+)?)\s*(s|sec|secs|seconds?|m|min|mins|minutes?|h|hr|hrs|hours?|d|days?)$",
        raw_str,
        re.IGNORECASE
    )
    if rel_match:
        val = float(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if unit.startswith("s"):
            target = now + timedelta(seconds=val)
            return target, f"Scheduled for {val} second(s) from now ({target.strftime('%Y-%m-%d %H:%M:%S %Z')})"
        elif unit.startswith("m"):
            target = now + timedelta(minutes=val)
            return target, f"Scheduled for {val} minute(s) from now ({target.strftime('%Y-%m-%d %H:%M:%S %Z')})"
        elif unit.startswith("h"):
            target = now + timedelta(hours=val)
            return target, f"Scheduled for {val} hour(s) from now ({target.strftime('%Y-%m-%d %H:%M:%S %Z')})"
        elif unit.startswith("d"):
            target = now + timedelta(days=val)
            return target, f"Scheduled for {val} day(s) from now ({target.strftime('%Y-%m-%d %H:%M:%S %Z')})"

    # 2. Check 'today at ...' or 'tomorrow at ...'
    day_match = re.match(
        r"^(today|tomorrow)\s+(?:at\s+)?(\d{1,2}(?::\d{2})?(?::\d{2})?\s*(?:am|pm)?)$",
        raw_str,
        re.IGNORECASE
    )
    if day_match:
        day_kw = day_match.group(1).lower()
        time_part = day_match.group(2)
        base_date = now.date() if day_kw == "today" else (now + timedelta(days=1)).date()
        parsed_time = dateutil_parser.parse(time_part).time()
        target = datetime.combine(base_date, parsed_time).replace(tzinfo=tz)
        return target, f"Scheduled for {day_kw} at {parsed_time.strftime('%H:%M:%S')} ({target.strftime('%Y-%m-%d %H:%M:%S %Z')})"

    # 3. Fallback to general dateutil parsing
    try:
        parsed = dateutil_parser.parse(raw_str)
        # If no timezone is specified, assign local/configured timezone
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed, f"Scheduled for {parsed.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    except Exception as e:
        raise ValueError(
            f"Could not parse scheduled time '{time_str}'. "
            f"Please use standard formats like 'YYYY-MM-DD HH:MM:SS' or relative formats like 'in 15 minutes'."
        ) from e
