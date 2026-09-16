"""End-to-end (minus the real LLM) coverage of the scheduling orchestrator:
FakeLLMProvider intent → deterministic date resolution → real DB busy
lookup → deterministic slot search."""

from __future__ import annotations

from odp.models import Meeting
from odp.models.time import from_utc_iso
from odp.repositories.meetings import MeetingsRepository
from odp.services.llm import FakeLLMProvider
from odp.services.scheduling.freebusy import BusyInterval, has_conflict
from odp.services.scheduling.schedule_service import suggest_meeting_slots

Y_FIRM_START = "2026-09-25T07:30:00Z"  # 10:30 Europe/Istanbul
Y_FIRM_END = "2026-09-25T09:00:00Z"  # 12:00 Europe/Istanbul


async def test_suggest_meeting_slots_avoids_existing_meeting(db_conn):
    repo = MeetingsRepository(db_conn)
    repo.create(
        Meeting(
            title="Y Firması",
            start_utc=Y_FIRM_START,
            end_utc=Y_FIRM_END,
            timezone="Europe/Istanbul",
            created_at="x",
            updated_at="x",
        )
    )

    provider = FakeLLMProvider()
    provider.add_json_response(
        "X müşterisi",
        {
            "duration_minutes": 90,
            "explicit_date": "2026-09-25",
            "day_of_week": None,
            "time_of_day_preference": "any",
            "earliest_local_time": None,
            "participant_hint": "X müşterisi",
        },
    )

    suggestion = await suggest_meeting_slots(
        db_conn,
        provider,
        text="Cuma günü X müşterisiyle 1.5 saatlik toplantı",
        model="gpt-oss:20b",
        timezone="Europe/Istanbul",
    )

    assert suggestion.target_date_iso == "2026-09-25"
    assert len(suggestion.slots) >= 1

    y_firm_busy = BusyInterval(start=from_utc_iso(Y_FIRM_START), end=from_utc_iso(Y_FIRM_END))
    for slot in suggestion.slots:
        conflict = has_conflict(BusyInterval(start=slot.start, end=slot.end), [y_firm_busy])
        assert conflict is False
