from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from odp.api.deps import get_db
from odp.api.schemas import MeetingCreate, TranscriptImportRequest
from odp.models import Meeting, Proposal, TranscriptSegment
from odp.models.time import utc_now_iso
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.services.transcription.text_import import build_segments

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


@router.post("/{meeting_id}/transcript/import-text", response_model=list[TranscriptSegment])
def import_transcript_text(
    meeting_id: str, body: TranscriptImportRequest, conn: sqlite3.Connection = Depends(get_db)
) -> list[TranscriptSegment]:
    """Manual stand-in for the audio -> Whisper pipeline (plan slice 2,
    not yet built): paste a transcript, get segments an extraction run
    can use today."""
    repo = MeetingsRepository(conn)
    if repo.get(meeting_id) is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    existing = repo.get_segments(meeting_id)
    segments = build_segments(meeting_id, body.text, start_seq=len(existing))
    if segments:
        repo.add_segments(segments)
    return segments


@router.get("/{meeting_id}/proposals", response_model=list[Proposal])
def get_pending_proposals(
    meeting_id: str, conn: sqlite3.Connection = Depends(get_db)
) -> list[Proposal]:
    return ProposalsRepository(conn).list_pending_for_meeting(meeting_id)
