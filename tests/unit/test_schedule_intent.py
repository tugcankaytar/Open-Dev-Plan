from __future__ import annotations

from datetime import date

import pytest

from odp.services.llm import FakeLLMProvider
from odp.services.scheduling.intent import (
    ScheduleIntent,
    parse_schedule_intent,
    resolve_target_date,
)


def test_resolve_target_date_prefers_explicit_date():
    intent = ScheduleIntent(duration_minutes=60, explicit_date="2026-10-01", day_of_week="friday")
    assert resolve_target_date(intent, reference_date=date(2026, 9, 16)) == date(2026, 10, 1)


def test_resolve_target_date_resolves_weekday_name_deterministically():
    # 2026-09-16 is a Wednesday; "friday" should resolve to 2026-09-18,
    # never computed by an LLM (see plan §1/#1: the draft got this wrong).
    intent = ScheduleIntent(duration_minutes=60, day_of_week="friday")
    assert date(2026, 9, 16).weekday() == 2  # sanity: Wednesday
    assert resolve_target_date(intent, reference_date=date(2026, 9, 16)) == date(2026, 9, 18)


def test_resolve_target_date_same_weekday_as_today_stays_today():
    intent = ScheduleIntent(duration_minutes=60, day_of_week="wednesday")
    today = date(2026, 9, 16)  # a Wednesday
    assert resolve_target_date(intent, reference_date=today) == today


def test_resolve_target_date_falls_back_to_reference_date_when_unspecified():
    intent = ScheduleIntent(duration_minutes=30)
    today = date(2026, 9, 16)
    assert resolve_target_date(intent, reference_date=today) == today


def test_resolve_target_date_rejects_unknown_weekday_name():
    intent = ScheduleIntent(duration_minutes=30, day_of_week="funday")
    with pytest.raises(ValueError, match="unrecognized"):
        resolve_target_date(intent, reference_date=date(2026, 9, 16))


async def test_parse_schedule_intent_uses_structured_output():
    provider = FakeLLMProvider()
    provider.add_json_response(
        "Cuma",
        {
            "duration_minutes": 90,
            "explicit_date": None,
            "day_of_week": "friday",
            "time_of_day_preference": "afternoon",
            "earliest_local_time": None,
            "participant_hint": "X müşterisi",
        },
    )

    intent = await parse_schedule_intent(
        provider,
        text="Cuma günü X müşterisiyle 1.5 saatlik bir toplantı ayarla",
        model="gpt-oss:20b",
    )

    assert intent.duration_minutes == 90
    assert intent.day_of_week == "friday"
    assert intent.time_of_day_preference == "afternoon"
