from __future__ import annotations

from datetime import UTC, datetime, timedelta

from odp.models import Meeting, ProposalKind, Task, TaskStatus
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.projects import ProjectsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.repositories.stats import StatsRepository
from odp.repositories.tasks import TasksRepository


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_dashboard_counts_reflects_seeded_data(db_conn):
    projects_repo = ProjectsRepository(db_conn)
    tasks_repo = TasksRepository(db_conn)
    meetings_repo = MeetingsRepository(db_conn)
    proposals_repo = ProposalsRepository(db_conn)

    projects_repo.create("Proje A")
    projects_repo.create("Proje B")

    now = datetime.now(UTC)
    tasks_repo.create(Task(title="Açık", created_at=_iso(now), updated_at=_iso(now)))
    tasks_repo.create(
        Task(
            title="Gecikmiş",
            due_utc=_iso(now - timedelta(days=2)),
            created_at=_iso(now),
            updated_at=_iso(now),
        )
    )
    tasks_repo.create(
        Task(title="Bitti", status=TaskStatus.done, created_at=_iso(now), updated_at=_iso(now))
    )

    meetings_repo.create(
        Meeting(
            title="M1",
            start_utc=_iso(now),
            end_utc=_iso(now + timedelta(minutes=30)),
            timezone="UTC",
            created_at=_iso(now),
            updated_at=_iso(now),
        )
    )

    proposals_repo.create(
        kind=ProposalKind.task,
        payload={"title": "x"},
        source_meeting_id=None,
        source_segment_ids=[],
        confidence=0.5,
        prompt_version="v1",
        model="m",
    )

    counts = StatsRepository(db_conn).dashboard_counts()

    assert counts["active_projects"] == 2
    assert counts["open_tasks"] == 2  # "Açık" + "Gecikmiş", not "Bitti"
    assert counts["overdue_tasks"] == 1
    assert counts["meetings"] == 1
    assert counts["pending_proposals"] == 1


def test_task_status_counts_includes_zero_for_missing_statuses(db_conn):
    tasks_repo = TasksRepository(db_conn)
    now = datetime.now(UTC)
    tasks_repo.create(Task(title="t1", created_at=_iso(now), updated_at=_iso(now)))

    counts = StatsRepository(db_conn).task_status_counts()

    assert counts == {"todo": 1, "in_progress": 0, "blocked": 0, "done": 0}


def test_weekly_activity_buckets_by_day(db_conn):
    tasks_repo = TasksRepository(db_conn)
    today = datetime.now(UTC)
    tasks_repo.create(Task(title="today", created_at=_iso(today), updated_at=_iso(today)))

    activity = StatsRepository(db_conn).weekly_activity(days=7)

    assert len(activity) == 7
    assert activity[-1]["date"] == today.date().isoformat()
    assert activity[-1]["created"] == 1
