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
    """Parse a stored/incoming UTC string back into an aware datetime.

    Accepts our own canonical no-fractional-seconds form as well as
    fractional-second variants (e.g. the browser's `Date.toISOString()`,
    which always emits milliseconds) — both are valid ISO-8601 for the
    same instant, and every write path should not have to hand-roll its
    own formatting to match ours exactly.
    """
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def normalize_utc_iso(s: str) -> str:
    """Reserialize any valid UTC ISO-8601 string to our canonical storage
    form — so a client-supplied timestamp (which may carry milliseconds)
    never ends up stored in a different shape than the ones this app
    writes itself. Mixed formats would still parse, but would sort
    incorrectly against each other as raw strings (SQL range queries and
    the frontend's plain string comparisons both rely on that ordering)."""
    return to_utc_iso(from_utc_iso(s))
