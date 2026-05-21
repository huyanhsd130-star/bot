"""Trading session and time utilities."""

from __future__ import annotations

from datetime import datetime, timezone

# Trading sessions in UTC
SESSIONS = {
    "sydney": (21, 6),    # 21:00 - 06:00 UTC
    "tokyo": (0, 9),      # 00:00 - 09:00 UTC
    "london": (7, 16),    # 07:00 - 16:00 UTC
    "new_york": (12, 21), # 12:00 - 21:00 UTC
}


def is_in_session(session_name: str, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    hour = now.hour
    start, end = SESSIONS.get(session_name.lower(), (0, 0))
    if start < end:
        return start <= hour < end
    # Overnight session (e.g., Sydney)
    return hour >= start or hour < end


def is_in_any_session(sessions: list[str], now: datetime | None = None) -> bool:
    return any(is_in_session(s, now) for s in sessions)


def is_weekend(now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    # Forex market closed from Friday 21:00 UTC to Sunday 21:00 UTC
    weekday = now.weekday()
    if weekday == 4 and now.hour >= 21:  # Friday after 21:00
        return True
    if weekday == 5:  # Saturday
        return True
    if weekday == 6 and now.hour < 21:  # Sunday before 21:00
        return True
    return False
