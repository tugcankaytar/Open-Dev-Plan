"""Orchestrates the scheduling flow: NL intent (LLM) → date resolution
(deterministic) → busy lookup (DB) → free-slot search (deterministic).

This is the module the API layer calls; it deliberately contains no LLM
math and no direct SQL — it composes the pieces in intent.py, solver.py,
freebusy.py, and repositories/meetings.py, each already unit-tested on
its own.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from odp.repositories.meetings import MeetingsRepository
from odp.services.llm.provider import LLMProvider
from odp.services.scheduling.freebusy import busy_intervals_from_meetings
from odp.services.scheduling.intent import (
    ScheduleIntent,
    parse_schedule_intent,
    resolve_target_date,
)
from odp.services.scheduling.solver import TimeSlot, find_free_slots


@dataclass(frozen=True, slots=True)
class ScheduleSuggestion:
    intent: ScheduleIntent
    target_date_iso: str
    slots: list[TimeSlot]


async def suggest_meeting_slots(
    conn: sqlite3.Connection,
    provider: LLMProvider,
    *,
    text: str,
    model: str,
    timezone: str,
    reference_datetime_utc: datetime | None = None,
    working_hours: tuple[time, time] = (time(9, 0), time(18, 0)),
    max_results: int = 5,
) -> ScheduleSuggestion:
    reference_datetime_utc = reference_datetime_utc or datetime.now(UTC)
    tz = ZoneInfo(timezone)

    intent = await parse_schedule_intent(provider, text=text, model=model)
    target_date = resolve_target_date(intent, reference_datetime_utc.astimezone(tz).date())

    day_start_utc = datetime.combine(target_date, time.min, tzinfo=tz).astimezone(UTC)
    day_end_utc = datetime.combine(target_date, time.max, tzinfo=tz).astimezone(UTC)

    meetings_repo = MeetingsRepository(conn)
    meetings = meetings_repo.list_in_range(
        day_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), day_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    busy = busy_intervals_from_meetings(meetings)

    not_before = None
    if intent.earliest_local_time:
        hh, mm = (int(p) for p in intent.earliest_local_time.split(":"))
        not_before = datetime.combine(target_date, time(hh, mm), tzinfo=tz).astimezone(UTC)
    elif intent.time_of_day_preference == "afternoon":
        not_before = datetime.combine(target_date, time(13, 0), tzinfo=tz).astimezone(UTC)
    elif intent.time_of_day_preference == "evening":
        not_before = datetime.combine(target_date, time(17, 0), tzinfo=tz).astimezone(UTC)

    slots = find_free_slots(
        busy=busy,
        day=target_date,
        tz=tz,
        duration=timedelta(minutes=intent.duration_minutes),
        working_hours=working_hours,
        not_before=not_before,
        max_results=max_results,
    )

    return ScheduleSuggestion(intent=intent, target_date_iso=target_date.isoformat(), slots=slots)
