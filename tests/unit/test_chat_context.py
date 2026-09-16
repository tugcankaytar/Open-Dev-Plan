from __future__ import annotations

from odp.models import Meeting, ProposalKind, ProposalStatus, Task
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.projects import ProjectsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.repositories.tasks import TasksRepository
from odp.services.chat.context import build_context

NOW = "2026-09-16T09:00:00Z"


def test_build_context_includes_projects_tasks_meetings_and_decisions(db_conn):
    ProjectsRepository(db_conn).create("Website Yenileme", "Kurumsal site")

    TasksRepository(db_conn).create(
        Task(title="Demo hazırla", owner="Mehmet", created_at=NOW, updated_at=NOW)
    )

    meeting = MeetingsRepository(db_conn).create(
        Meeting(
            title="Planlama Toplantısı",
            start_utc=NOW,
            end_utc="2026-09-16T09:30:00Z",
            timezone="Europe/Istanbul",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    proposals_repo = ProposalsRepository(db_conn)
    summary_proposal = proposals_repo.create(
        kind=ProposalKind.summary,
        payload={"summary": "Demo hazırlığı ve bütçe konuşuldu."},
        source_meeting_id=meeting.id,
        source_segment_ids=[],
        confidence=None,
        prompt_version="summary/v1/x",
        model="gpt-oss:20b",
    )
    proposals_repo.resolve(summary_proposal.id, status=ProposalStatus.approved)

    decision_proposal = proposals_repo.create(
        kind=ProposalKind.decision,
        payload={"summary": "Bütçe onaylandı."},
        source_meeting_id=meeting.id,
        source_segment_ids=[],
        confidence=0.9,
        prompt_version="decisions/v1/x",
        model="gpt-oss:20b",
    )
    proposals_repo.resolve(decision_proposal.id, status=ProposalStatus.approved)

    context = build_context(db_conn, timezone="Europe/Istanbul")

    assert "Website Yenileme" in context
    assert "Demo hazırla" in context and "Mehmet" in context
    assert "Planlama Toplantısı" in context
    assert "Demo hazırlığı ve bütçe konuşuldu." in context
    assert "Bütçe onaylandı." in context
    assert "Bugünün tarihi" in context


def test_build_context_handles_empty_database(db_conn):
    context = build_context(db_conn, timezone="UTC")
    assert "Aktif projeler" in context
    assert "(yok)" in context


def test_build_context_excludes_rejected_decisions(db_conn):
    proposals_repo = ProposalsRepository(db_conn)
    rejected = proposals_repo.create(
        kind=ProposalKind.decision,
        payload={"summary": "Reddedilen karar metni"},
        source_meeting_id=None,
        source_segment_ids=[],
        confidence=0.5,
        prompt_version="decisions/v1/x",
        model="gpt-oss:20b",
    )
    proposals_repo.resolve(rejected.id, status=ProposalStatus.rejected)

    context = build_context(db_conn, timezone="UTC")

    assert "Reddedilen karar metni" not in context
