"""Round-trip coverage for .ics export/import (plan §8): what we export
must come back as the same meeting when re-imported, RRULE and TZ
included."""

from __future__ import annotations

from odp.models import Meeting
from odp.services.calendar import export_meetings_to_ics, import_ics


def _sample_meeting(**overrides: object) -> Meeting:
    defaults: dict[str, object] = dict(
        title="Haftalık Standup",
        start_utc="2026-09-22T07:30:00Z",
        end_utc="2026-09-22T08:00:00Z",
        timezone="Europe/Istanbul",
        rrule="FREQ=WEEKLY;BYDAY=TU",
        location_link="https://meet.jit.si/odp-abc123",
        participants=["alice@example.com", "bob@example.com"],
        created_at="2026-09-16T00:00:00Z",
        updated_at="2026-09-16T00:00:00Z",
    )
    defaults.update(overrides)
    return Meeting(**defaults)  # type: ignore[arg-type]


def test_export_produces_valid_ics_bytes():
    ics_bytes = export_meetings_to_ics([_sample_meeting()])
    text = ics_bytes.decode("utf-8")
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VEVENT" in text
    assert "SUMMARY:Haftalık Standup" in text
    assert "RRULE:FREQ=WEEKLY;BYDAY=TU" in text


def test_round_trip_preserves_title_time_rrule_and_participants():
    original = _sample_meeting()
    ics_bytes = export_meetings_to_ics([original])

    imported = import_ics(ics_bytes, default_timezone="Europe/Istanbul")

    assert len(imported) == 1
    result = imported[0]
    assert result.title == original.title
    assert result.start_utc == original.start_utc
    assert result.end_utc == original.end_utc
    assert result.rrule == original.rrule
    assert result.location_link == original.location_link
    assert set(result.participants) == set(original.participants)


def test_import_handles_ics_with_no_rrule_or_attendees():
    meeting = _sample_meeting(rrule=None, participants=[])
    ics_bytes = export_meetings_to_ics([meeting])

    imported = import_ics(ics_bytes, default_timezone="Europe/Istanbul")

    assert imported[0].rrule is None
    assert imported[0].participants == []


def test_export_multiple_meetings_round_trips_all():
    meetings = [
        _sample_meeting(
            title="Toplantı A", start_utc="2026-09-22T07:00:00Z", end_utc="2026-09-22T07:30:00Z"
        ),
        _sample_meeting(
            title="Toplantı B", start_utc="2026-09-23T07:00:00Z", end_utc="2026-09-23T07:30:00Z"
        ),
    ]
    ics_bytes = export_meetings_to_ics(meetings)
    imported = import_ics(ics_bytes, default_timezone="Europe/Istanbul")

    assert {m.title for m in imported} == {"Toplantı A", "Toplantı B"}
