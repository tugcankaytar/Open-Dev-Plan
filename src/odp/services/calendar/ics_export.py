"""Export meetings to RFC-5545 `.ics`.

Plain library use, no LLM anywhere in this file — a calendar file is
either correct or it silently corrupts someone's schedule, which is
exactly the kind of thing this project keeps out of the model's hands
(plan §1/#2 makes the same call for meeting links).
"""

from __future__ import annotations

from datetime import UTC, datetime

from icalendar import Calendar, Event
from icalendar.prop import vRecur

from odp.models import Meeting
from odp.models.time import from_utc_iso

PRODID = "-//Open-Dev-Plan//odp 0.1//TR"


def meeting_to_vevent(meeting: Meeting) -> Event:
    event = Event()
    event.add("uid", f"{meeting.id}@open-dev-plan")
    event.add("summary", meeting.title)
    event.add("dtstart", from_utc_iso(meeting.start_utc))
    event.add("dtend", from_utc_iso(meeting.end_utc))
    event.add("dtstamp", datetime.now(UTC))
    event.add("last-modified", from_utc_iso(meeting.updated_at))

    if meeting.rrule:
        event.add("rrule", vRecur.from_ical(meeting.rrule))
    if meeting.location_link:
        event.add("location", meeting.location_link)
    for participant in meeting.participants:
        value = f"mailto:{participant}" if "@" in participant else participant
        event.add("attendee", value)

    return event


def export_meetings_to_ics(meetings: list[Meeting]) -> bytes:
    """Build a single `.ics` file (VCALENDAR) containing one VEVENT per meeting."""
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    for meeting in meetings:
        cal.add_component(meeting_to_vevent(meeting))
    return bytes(cal.to_ical())
