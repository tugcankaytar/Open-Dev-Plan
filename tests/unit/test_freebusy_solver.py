"""Regression coverage for the draft plan's scheduling bug (plan §1/#1):
an LLM once suggested a 10:30-12:30 slot against a 10:30-12:00 busy block.
Every test here is pure deterministic code — no LLM involved."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from odp.services.scheduling.freebusy import BusyInterval, has_conflict, merge_intervals
from odp.services.scheduling.solver import find_free_slots

TZ = ZoneInfo("Europe/Istanbul")
FRIDAY = date(2026, 9, 25)  # verified: Sept 22 2026 is a Tuesday, so +3 days is Friday


def _istanbul(hour: int, minute: int, day: date = FRIDAY) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ).astimezone(UTC)


def test_the_drafts_overlapping_suggestion_is_flagged_as_a_conflict():
    """This is exactly the scenario from the original draft plan: a firm's
    10:30-12:00 meeting is booked, and the (LLM-authored) suggestion was
    10:30-12:30 — a direct overlap that the draft's own example missed."""
    y_firm_meeting = BusyInterval(start=_istanbul(10, 30), end=_istanbul(12, 0))
    drafts_suggestion = BusyInterval(start=_istanbul(10, 30), end=_istanbul(12, 30))

    assert has_conflict(drafts_suggestion, [y_firm_meeting]) is True


def test_merge_intervals_coalesces_overlapping_and_adjacent():
    a = BusyInterval(start=_istanbul(9, 0), end=_istanbul(10, 0))
    b = BusyInterval(start=_istanbul(9, 30), end=_istanbul(10, 30))  # overlaps a
    c = BusyInterval(start=_istanbul(11, 0), end=_istanbul(12, 0))  # separate

    merged = merge_intervals([a, b, c])

    assert len(merged) == 2
    assert merged[0].start == _istanbul(9, 0)
    assert merged[0].end == _istanbul(10, 30)
    assert merged[1] == c


def test_find_free_slots_never_returns_a_conflicting_slot():
    y_firm_meeting = BusyInterval(start=_istanbul(10, 30), end=_istanbul(12, 0))

    slots = find_free_slots(
        busy=[y_firm_meeting],
        day=FRIDAY,
        tz=TZ,
        duration=timedelta(hours=1.5),
        working_hours=(time(9, 0), time(18, 0)),
    )

    for slot in slots:
        assert has_conflict(BusyInterval(start=slot.start, end=slot.end), [y_firm_meeting]) is False


def test_find_free_slots_lands_right_after_meeting_when_too_long_to_fit_before():
    y_firm_meeting = BusyInterval(start=_istanbul(10, 30), end=_istanbul(12, 0))

    # 2.5h doesn't fit in the 09:00-10:30 gap (90 min), so the first
    # available slot must be right after the meeting ends, at 12:00.
    slots = find_free_slots(
        busy=[y_firm_meeting],
        day=FRIDAY,
        tz=TZ,
        duration=timedelta(hours=2.5),
        working_hours=(time(9, 0), time(18, 0)),
    )

    assert len(slots) >= 1
    assert slots[0].start == _istanbul(12, 0)
    assert slots[0].end == _istanbul(14, 30)


def test_find_free_slots_respects_not_before():
    slots = find_free_slots(
        busy=[],
        day=FRIDAY,
        tz=TZ,
        duration=timedelta(hours=1),
        working_hours=(time(9, 0), time(18, 0)),
        not_before=_istanbul(13, 0),
    )

    assert slots[0].start == _istanbul(13, 0)


def test_find_free_slots_returns_nothing_when_day_is_fully_booked():
    full_day = BusyInterval(start=_istanbul(9, 0), end=_istanbul(18, 0))

    slots = find_free_slots(
        busy=[full_day],
        day=FRIDAY,
        tz=TZ,
        duration=timedelta(minutes=30),
        working_hours=(time(9, 0), time(18, 0)),
    )

    assert slots == []
