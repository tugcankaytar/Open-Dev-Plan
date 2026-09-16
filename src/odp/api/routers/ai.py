"""The AI-facing endpoints: trigger extraction, resolve proposals, and
get a schedule suggestion. Kept separate from meetings.py/tasks.py CRUD
because everything here either produces a `Proposal` or consumes one —
never writes a domain table directly except through resolve_proposal().
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from odp.api.deps import get_db, get_job_queue, get_llm_provider, get_settings_dep
from odp.api.schemas import (
    ProposalResolveRequest,
    ScheduleSuggestRequest,
    ScheduleSuggestResponse,
    TimeSlotOut,
)
from odp.config import Settings
from odp.jobs.queue import JobQueue
from odp.models import Job, JobType, Proposal
from odp.models.time import to_utc_iso
from odp.repositories.app_settings import AppSettingsRepository
from odp.services import events
from odp.services.llm.provider import LLMProvider
from odp.services.proposals import resolve_proposal
from odp.services.proposals.resolve import ProposalResolutionError
from odp.services.scheduling.schedule_service import suggest_meeting_slots

router = APIRouter(prefix="/api", tags=["ai"])


@router.post("/meetings/{meeting_id}/extract", response_model=Job, status_code=202)
def trigger_extraction(meeting_id: str, queue: JobQueue = Depends(get_job_queue)) -> Job:
    return queue.enqueue(JobType.extraction, {"meeting_id": meeting_id})


@router.post("/proposals/{proposal_id}/resolve", response_model=Proposal)
async def resolve_proposal_endpoint(
    proposal_id: str,
    body: ProposalResolveRequest,
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> Proposal:
    try:
        resolved = await resolve_proposal(
            conn,
            proposal_id=proposal_id,
            action=body.action,
            payload_override=body.payload,
            default_timezone=settings.default_timezone,
        )
    except ProposalResolutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    events.publish("proposals")
    return resolved


@router.post("/schedule/suggest", response_model=ScheduleSuggestResponse)
async def schedule_suggest(
    body: ScheduleSuggestRequest,
    conn: sqlite3.Connection = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings_dep),
) -> ScheduleSuggestResponse:
    model = AppSettingsRepository(conn).get_active_model(settings.extraction_model)
    suggestion = await suggest_meeting_slots(
        conn,
        provider,
        text=body.text,
        model=model,
        timezone=settings.default_timezone,
    )
    return ScheduleSuggestResponse(
        target_date=suggestion.target_date_iso,
        duration_minutes=suggestion.intent.duration_minutes,
        participant_hint=suggestion.intent.participant_hint,
        slots=[
            TimeSlotOut(start_utc=to_utc_iso(s.start), end_utc=to_utc_iso(s.end))
            for s in suggestion.slots
        ],
    )
