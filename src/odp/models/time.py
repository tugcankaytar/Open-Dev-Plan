"""Time helpers.

Every timestamp stored in the database is UTC, ISO-8601, with a trailing
``Z`` — never a naive local time (plan §1/#6). Conversion to/from the
user's IANA zone happens only at the UI/API boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Current instant as an ISO-8601 UTC string, e.g. 2026-09-16T12:00:00Z."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc_iso(dt: datetime) -> str:
    """Serialize an aware datetime to our storage format. Raises on naive input."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime passed to to_utc_iso(); attach a tzinfo first")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_utc_iso(s: str) -> datetime:
    """Parse one of our stored UTC strings back into an aware datetime."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
