"""The human-approval gate itself: turn a `Proposal` into a domain row
(or nothing, if rejected) — the only place that's allowed to happen
(plan §1/#5).

Due-date resolution for approved task proposals reuses the same
deterministic weekday resolver as scheduling (odp.services.common.dates)
— the model named a day, this function is the only place a calendar date
gets computed from it.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from odp.models import Proposal, ProposalKind, ProposalStatus, Task
from odp.models.time import from_utc_iso, to_utc_iso, utc_now_iso
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.repositories.tasks import TasksRepository
from odp.repositories.training_examples import TrainingExamplesRepository
from odp.services.common.dates import resolve_weekday

ResolveAction = Literal["approve", "edit", "reject"]


class ProposalResolutionError(Exception):
    pass


def _resolve_due_utc(
    payload: dict[str, Any], meeting_local_date: date, timezone: str
) -> str | None:
    explicit = payload.get("due_explicit_date")
    if explicit:
        due_date = date.fromisoformat(explicit)
    elif payload.get("due_day_of_week"):
        due_date = resolve_weekday(payload["due_day_of_week"], meeting_local_date)
    else:
        return None

    # "Due by <date>" is interpreted as end-of-day in the meeting's timezone.
    due_dt = datetime.combine(due_date, time(23, 59, 59), tzinfo=ZoneInfo(timezone))
    return to_utc_iso(due_dt)


def _training_kind(action: ResolveAction) -> str:
    return "dpo_pair" if action == "reject" else "sft"


async def resolve_proposal(
    conn: sqlite3.Connection,
    *,
    proposal_id: str,
    action: ResolveAction,
    payload_override: dict[str, Any] | None = None,
    default_timezone: str = "UTC",
) -> Proposal:
    proposals_repo = ProposalsRepository(conn)
    tasks_repo = TasksRepository(conn)
    meetings_repo = MeetingsRepository(conn)
    training_repo = TrainingExamplesRepository(conn)

    proposal = proposals_repo.get(proposal_id)
    if proposal is None:
        raise ProposalResolutionError(f"no such proposal: {proposal_id}")
    if proposal.status != ProposalStatus.pending:
        msg = f"proposal {proposal_id} already resolved ({proposal.status})"
        raise ProposalResolutionError(msg)

    effective_payload = payload_override if payload_override is not None else proposal.payload
    resolved_task_id: str | None = None

    if action in ("approve", "edit") and proposal.kind == ProposalKind.task:
        meeting = (
            meetings_repo.get(proposal.source_meeting_id) if proposal.source_meeting_id else None
        )
        timezone = meeting.timezone if meeting else default_timezone
        reference_date = (
            from_utc_iso(meeting.start_utc).astimezone(ZoneInfo(timezone)).date()
            if meeting
            else datetime.now(ZoneInfo(timezone)).date()
        )
        due_utc = _resolve_due_utc(effective_payload, reference_date, timezone)
        source_segment_id = proposal.source_segment_ids[0] if proposal.source_segment_ids else None

        now = utc_now_iso()
        task = tasks_repo.create(
            Task(
                project_id=meeting.project_id if meeting else None,
                meeting_id=proposal.source_meeting_id,
                title=effective_payload["title"],
                owner=effective_payload.get("owner"),
                due_utc=due_utc,
                source_segment_id=source_segment_id,
                confidence=effective_payload.get("confidence"),
                created_at=now,
                updated_at=now,
            )
        )
        resolved_task_id = task.id

    status_by_action: dict[ResolveAction, ProposalStatus] = {
        "approve": ProposalStatus.approved,
        "edit": ProposalStatus.edited,
        "reject": ProposalStatus.rejected,
    }
    status = status_by_action[action]

    resolved = proposals_repo.resolve(
        proposal_id,
        status=status,
        resolved_payload=payload_override,
        resolved_task_id=resolved_task_id,
    )
    assert resolved is not None

    excerpt_segments = meetings_repo.get_segments_by_ids(proposal.source_segment_ids)
    transcript_excerpt = " ".join(s.text for s in excerpt_segments)
    training_repo.record(
        proposal_id=proposal.id,
        kind=_training_kind(action),
        transcript_excerpt=transcript_excerpt,
        model_output=proposal.payload,
        user_correction=payload_override,
    )

    return resolved
