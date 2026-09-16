"""Shared weekday-name -> date resolution.

Used by both the scheduling intent parser (services/scheduling/intent.py)
and action-item due-date extraction (services/extraction/actions.py): in
both places the LLM is only allowed to name a weekday, never compute a
calendar date — see plan §1/#1 for why that split exists.
"""

from __future__ import annotations

from datetime import date, timedelta

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    # Turkish weekday names, since this is the app's primary language.
    "pazartesi": 0,
    "salı": 1,
    "sali": 1,
    "çarşamba": 2,
    "carsamba": 2,
    "perşembe": 3,
    "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}


def resolve_weekday(day_of_week: str, reference_date: date) -> date:
    """Next occurrence of `day_of_week` on/after `reference_date`.

    `reference_date` itself counts if it already falls on that weekday.
    Raises ValueError for a name not in WEEKDAY_INDEX.
    """
    key = day_of_week.strip().lower()
    if key not in WEEKDAY_INDEX:
        raise ValueError(f"unrecognized day_of_week: {day_of_week!r}")
    target = WEEKDAY_INDEX[key]
    days_ahead = (target - reference_date.weekday()) % 7
    return reference_date + timedelta(days=days_ahead)
