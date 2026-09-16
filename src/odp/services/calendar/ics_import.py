"""Import meetings from an externally-produced `.ics` file.

Returns fresh `Meeting` objects (new local ids) — the caller decides
whether/how to persist them (e.g. de-duplicating against an existing
`uid`, which we preserve in `location_link`... no: we don't invent a
field for it. Callers that need dedup can match on title+start_utc, or
this module can be extended with a dedicated `external_uid` column
later).
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from icalendar import Calendar

from odp.models import Meeting, MeetingStatus
from odp.models.time import to_utc_iso, utc_now_iso


def _as_aware_datetime(value: object, default_timezone: str) -> datetime:
    """Normalize an icalendar DTSTART/DTEND value to an aware UTC-bound datetime.

    Handles the three shapes icalendar hands back: an aware datetime, a
    naive datetime (assume `default_timezone`), or a plain `date` (all-day
    event — midnight in `default_timezone`).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=ZoneInfo(default_timezone))
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=ZoneInfo(default_timezone))
    raise TypeError(f"unsupported DTSTART/DTEND value: {value!r}")


def import_ics(data: bytes, *, default_timezone: str = "UTC") -> list[Meeting]:
    calendar = Calendar.from_ical(data)
    meetings: list[Meeting] = []

    for component in calendar.walk("VEVENT"):
        start = _as_aware_datetime(component.get("dtstart").dt, default_timezone)
        end_prop = component.get("dtend")
        end = _as_aware_datetime(end_prop.dt, default_timezone) if end_prop else start

        rrule_prop = component.get("rrule")
        rrule = rrule_prop.to_ical().decode("ascii") if rrule_prop else None

        location = component.get("location")
        attendees_raw = component.get("attendee")
        if attendees_raw is None:
            participants: list[str] = []
        elif isinstance(attendees_raw, list):
            participants = [str(a).removeprefix("mailto:") for a in attendees_raw]
        else:
            participants = [str(attendees_raw).removeprefix("mailto:")]

        now = utc_now_iso()
        meetings.append(
            Meeting(
                title=str(component.get("summary", "İçe aktarılan toplantı")),
                start_utc=to_utc_iso(start),
                end_utc=to_utc_iso(end),
                timezone=default_timezone,
                rrule=rrule,
                location_link=str(location) if location else None,
                participants=participants,
                status=MeetingStatus.scheduled,
                created_at=now,
                updated_at=now,
            )
        )

    return meetings
