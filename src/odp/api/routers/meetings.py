from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from odp.api.deps import get_db
from odp.api.schemas import MeetingCreate
from odp.models import Meeting, Proposal, TranscriptSegment
from odp.models.time import utc_now_iso
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.proposals import ProposalsRepository

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.post("", response_model=Meeting, status_code=201)
def create_meeting(body: MeetingCreate, conn: sqlite3.Connection = Depends(get_db)) -> Meeting:
    now = utc_now_iso()
    meeting = Meeting(
        title=body.title,
        start_utc=body.start_utc,
        end_utc=body.end_utc,
        timezone=body.timezone,
        project_id=body.project_id,
        rrule=body.rrule,
        location_link=body.location_link,
        participants=body.participants,
        created_at=now,
        updated_at=now,
    )
    return MeetingsRepository(conn).create(meeting)


@router.get("", response_model=list[Meeting])
def list_meetings(conn: sqlite3.Connection = Depends(get_db)) -> list[Meeting]:
    return MeetingsRepository(conn).list_all()


@router.get("/{meeting_id}", response_model=Meeting)
def get_meeting(meeting_id: str, conn: sqlite3.Connection = Depends(get_db)) -> Meeting:
    meeting = MeetingsRepository(conn).get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(meeting_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    MeetingsRepository(conn).delete(meeting_id)


@router.get("/{meeting_id}/transcript", response_model=list[TranscriptSegment])
def get_transcript(
    meeting_id: str, conn: sqlite3.Connection = Depends(get_db)
) -> list[TranscriptSegment]:
    return MeetingsRepository(conn).get_segments(meeting_id)


@router.get("/{meeting_id}/proposals", response_model=list[Proposal])
def get_pending_proposals(
    meeting_id: str, conn: sqlite3.Connection = Depends(get_db)
) -> list[Proposal]:
    return ProposalsRepository(conn).list_pending_for_meeting(meeting_id)
