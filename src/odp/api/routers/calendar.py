from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from odp.api.deps import get_db, get_settings_dep
from odp.api.schemas import IcsImportRequest
from odp.config import Settings
from odp.models import Meeting
from odp.repositories.meetings import MeetingsRepository
from odp.services import events
from odp.services.calendar import export_meetings_to_ics, import_ics

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/export.ics")
def export_calendar(conn: sqlite3.Connection = Depends(get_db)) -> Response:
    meetings = MeetingsRepository(conn).list_all()
    ics_bytes = export_meetings_to_ics(meetings)
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=open-dev-plan.ics"},
    )


@router.post("/import", response_model=list[Meeting])
def import_calendar(
    body: IcsImportRequest,
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> list[Meeting]:
    imported = import_ics(body.ics_text.encode("utf-8"), default_timezone=settings.default_timezone)
    if body.persist:
        repo = MeetingsRepository(conn)
        imported = [repo.create(m) for m in imported]
        if imported:
            events.publish("meetings")
    return imported
