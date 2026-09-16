"""The human-approval gate (plan §1/#5): approve turns a task proposal
into a real Task with a deterministically-resolved due date; reject and
edit never silently lose the model's original output (training_examples
captures it either way)."""

from __future__ import annotations

import pytest

from odp.models import Meeting, MeetingStatus, ProposalKind, ProposalStatus
from odp.models.time import from_utc_iso
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.repositories.tasks import TasksRepository
from odp.services.proposals import resolve_proposal
from odp.services.proposals.resolve import ProposalResolutionError


def _make_meeting(db_conn, **overrides):
    defaults = dict(
        title="Planlama",
        start_utc="2026-09-16T09:00:00Z",  # Wednesday in Europe/Istanbul
        end_utc="2026-09-16T09:30:00Z",
        timezone="Europe/Istanbul",
        status=MeetingStatus.processed,
        created_at="x",
        updated_at="x",
    )
    defaults.update(overrides)
    return MeetingsRepository(db_conn).create(Meeting(**defaults))


async def test_approve_task_proposal_creates_task_with_resolved_due_date(db_conn):
    meeting = _make_meeting(db_conn)
    proposals_repo = ProposalsRepository(db_conn)
    proposal = proposals_repo.create(
        kind=ProposalKind.task,
        payload={
            "title": "Demo hazırla",
            "owner": "Mehmet",
            "due_day_of_week": "friday",
            "due_explicit_date": None,
            "source_quote": "ben hazırlarım",
            "confidence": 0.9,
        },
        source_meeting_id=meeting.id,
        source_segment_ids=[],
        confidence=0.9,
        prompt_version="action_items/v1/deadbeef",
        model="gpt-oss:20b",
    )

    resolved = await resolve_proposal(db_conn, proposal_id=proposal.id, action="approve")

    assert resolved.status == ProposalStatus.approved
    assert resolved.resolved_task_id is not None

    task = TasksRepository(db_conn).get(resolved.resolved_task_id)
    assert task is not None
    assert task.title == "Demo hazırla"
    assert task.owner == "Mehmet"
    # 2026-09-16 is Wednesday in Europe/Istanbul; "friday" -> 2026-09-18, 23:59:59 local -> UTC.
    assert task.due_utc is not None
    local_due = from_utc_iso(task.due_utc)
    assert local_due.date().isoformat() >= "2026-09-18"


async def test_edit_task_proposal_uses_overridden_payload(db_conn):
    meeting = _make_meeting(db_conn)
    proposals_repo = ProposalsRepository(db_conn)
    proposal = proposals_repo.create(
        kind=ProposalKind.task,
        payload={
            "title": "Yanlış başlık",
            "owner": None,
            "due_day_of_week": None,
            "due_explicit_date": None,
            "source_quote": "q",
            "confidence": 0.5,
        },
        source_meeting_id=meeting.id,
        source_segment_ids=[],
        confidence=0.5,
        prompt_version="action_items/v1/deadbeef",
        model="gpt-oss:20b",
    )

    resolved = await resolve_proposal(
        db_conn,
        proposal_id=proposal.id,
        action="edit",
        payload_override={
            "title": "Doğru başlık",
            "owner": "Ayşe",
            "due_day_of_week": None,
            "due_explicit_date": None,
            "source_quote": "q",
            "confidence": 0.5,
        },
    )

    assert resolved.status == ProposalStatus.edited
    task = TasksRepository(db_conn).get(resolved.resolved_task_id)
    assert task is not None
    assert task.title == "Doğru başlık"
    assert task.owner == "Ayşe"


async def test_reject_proposal_creates_no_task(db_conn):
    proposals_repo = ProposalsRepository(db_conn)
    proposal = proposals_repo.create(
        kind=ProposalKind.task,
        payload={"title": "Uydurma görev", "confidence": 0.2, "source_quote": "q"},
        source_meeting_id=None,
        source_segment_ids=[],
        confidence=0.2,
        prompt_version="action_items/v1/deadbeef",
        model="gpt-oss:20b",
    )

    resolved = await resolve_proposal(db_conn, proposal_id=proposal.id, action="reject")

    assert resolved.status == ProposalStatus.rejected
    assert resolved.resolved_task_id is None
    task_count = db_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    assert task_count == 0

    training_rows = db_conn.execute(
        "SELECT kind FROM training_examples WHERE proposal_id = ?", (proposal.id,)
    ).fetchall()
    assert [r[0] for r in training_rows] == ["dpo_pair"]


async def test_approve_decision_proposal_creates_no_task(db_conn):
    proposals_repo = ProposalsRepository(db_conn)
    proposal = proposals_repo.create(
        kind=ProposalKind.decision,
        payload={"summary": "Karar verildi", "source_quote": "q", "confidence": 0.7},
        source_meeting_id=None,
        source_segment_ids=[],
        confidence=0.7,
        prompt_version="decisions/v1/deadbeef",
        model="gpt-oss:20b",
    )

    resolved = await resolve_proposal(db_conn, proposal_id=proposal.id, action="approve")

    assert resolved.status == ProposalStatus.approved
    assert resolved.resolved_task_id is None
    assert db_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


async def test_resolving_an_already_resolved_proposal_raises(db_conn):
    proposals_repo = ProposalsRepository(db_conn)
    proposal = proposals_repo.create(
        kind=ProposalKind.decision,
        payload={"summary": "x", "source_quote": "q", "confidence": 0.5},
        source_meeting_id=None,
        source_segment_ids=[],
        confidence=0.5,
        prompt_version="decisions/v1/deadbeef",
        model="gpt-oss:20b",
    )
    await resolve_proposal(db_conn, proposal_id=proposal.id, action="approve")

    with pytest.raises(ProposalResolutionError):
        await resolve_proposal(db_conn, proposal_id=proposal.id, action="approve")


async def test_resolving_unknown_proposal_raises(db_conn):
    with pytest.raises(ProposalResolutionError):
        await resolve_proposal(db_conn, proposal_id="does-not-exist", action="approve")
