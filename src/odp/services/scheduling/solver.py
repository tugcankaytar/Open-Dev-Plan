"""Deterministic free-slot finder.

Given merged busy intervals for a day and a requested duration, returns
candidate slots inside working hours that do not conflict with anything
— zero LLM involvement (see freebusy.py's module docstring for why that
matters). The model's only job upstream of this is turning "1.5 hours on
Wednesday afternoon" into a `ScheduleIntent` (intent.py); this module
turns that intent into an answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from odp.services.scheduling.freebusy import BusyInterval, has_conflict, merge_intervals


@dataclass(frozen=True, slots=True)
class TimeSlot:
    start: datetime  # tz-aware, UTC
    end: datetime


def find_free_slots(
    *,
    busy: list[BusyInterval],
    day: date,
    tz: ZoneInfo,
    duration: timedelta,
    working_hours: tuple[time, time] = (time(9, 0), time(18, 0)),
    not_before: datetime | None = None,
    buffer: timedelta = timedelta(0),
    max_results: int = 5,
) -> list[TimeSlot]:
    """Find up to `max_results` non-conflicting slots of `duration` on `day`.

    Slots are returned earliest-first, each snapped to the start of the
    gap it was found in (so back-to-back scheduling right after a prior
    meeting is preferred over an arbitrary later time — matching what a
    person would actually want, per the plan's "right after Y's meeting"
    scenario).
    """
    if duration <= timedelta(0):
        raise ValueError("duration must be positive")

    day_start_local = datetime.combine(day, working_hours[0], tzinfo=tz)
    day_end_local = datetime.combine(day, working_hours[1], tzinfo=tz)

    day_start_utc = day_start_local.astimezone(UTC)
    day_end_utc = day_end_local.astimezone(UTC)
    if not_before is not None and not_before > day_start_utc:
        day_start_utc = not_before

    # Buffer expands each busy interval so we don't schedule flush against
    # an existing meeting when a gap is requested (e.g. 5 min breathing room).
    padded_busy = [BusyInterval(start=b.start - buffer, end=b.end + buffer) for b in busy]
    relevant = merge_intervals(
        [b for b in padded_busy if b.overlaps(BusyInterval(start=day_start_utc, end=day_end_utc))]
    )

    gaps: list[BusyInterval] = []
    cursor = day_start_utc
    for busy_block in relevant:
        clipped_start = max(busy_block.start, day_start_utc)
        clipped_end = min(busy_block.end, day_end_utc)
        if clipped_start > cursor:
            gaps.append(BusyInterval(start=cursor, end=clipped_start))
        cursor = max(cursor, clipped_end)
    if cursor < day_end_utc:
        gaps.append(BusyInterval(start=cursor, end=day_end_utc))

    results: list[TimeSlot] = []
    for gap in gaps:
        if gap.end - gap.start >= duration:
            candidate = TimeSlot(start=gap.start, end=gap.start + duration)
            # Defensive re-check: the slot we're about to offer must not
            # conflict with the *unpadded* original busy list either.
            if not has_conflict(BusyInterval(start=candidate.start, end=candidate.end), busy):
                results.append(candidate)
        if len(results) >= max_results:
            break

    return results
