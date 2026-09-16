"""Interval arithmetic for calendar conflicts.

This is the whole point of plan §1/#1: the draft plan asked an LLM to find
a free slot and it produced a suggestion overlapping an existing meeting.
Everything in this module is plain, deterministic code with no model call
anywhere near it — conflict detection and slot-finding are math, not
generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from odp.models import Meeting
from odp.models.time import from_utc_iso


@dataclass(frozen=True, slots=True)
class BusyInterval:
    start: datetime  # tz-aware, UTC
    end: datetime

    def overlaps(self, other: BusyInterval) -> bool:
        return self.start < other.end and other.start < self.end


def busy_intervals_from_meetings(meetings: list[Meeting]) -> list[BusyInterval]:
    """Build sorted, merged busy intervals from a list of Meeting rows."""
    intervals = [
        BusyInterval(start=from_utc_iso(m.start_utc), end=from_utc_iso(m.end_utc)) for m in meetings
    ]
    return merge_intervals(intervals)


def merge_intervals(intervals: list[BusyInterval]) -> list[BusyInterval]:
    """Sort and coalesce overlapping/adjacent intervals into a minimal set."""
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda i: i.start)
    merged = [ordered[0]]
    for current in ordered[1:]:
        last = merged[-1]
        if current.start <= last.end:
            merged[-1] = BusyInterval(start=last.start, end=max(last.end, current.end))
        else:
            merged.append(current)
    return merged


def has_conflict(candidate: BusyInterval, busy: list[BusyInterval]) -> bool:
    """True if `candidate` overlaps any busy interval.

    This is the exact check the original draft plan's LLM-based scheduler
    failed to apply — a 10:30–12:30 suggestion against a 10:30–12:00 busy
    block must come back True here.
    """
    return any(candidate.overlaps(b) for b in busy)
