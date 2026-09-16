"""Covers the task-detail additions: priority, start_utc, tags, and the
checklist sub-table (plus its computed checklist_total/checklist_done
aggregate on Task)."""

from __future__ import annotations

from odp.models import Task, TaskPriority
from odp.models.time import utc_now_iso
from odp.repositories.tasks import TasksRepository

NOW = utc_now_iso()


def _task(**overrides: object) -> Task:
    defaults: dict[str, object] = dict(title="Görev", created_at=NOW, updated_at=NOW)
    defaults.update(overrides)
    return Task(**defaults)  # type: ignore[arg-type]


def test_create_persists_priority_start_and_tags(db_conn):
    repo = TasksRepository(db_conn)
    created = repo.create(
        _task(
            priority=TaskPriority.high,
            start_utc="2026-09-20T09:00:00Z",
            tags=["backend", "acil"],
        )
    )

    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.priority == TaskPriority.high
    assert fetched.start_utc == "2026-09-20T09:00:00Z"
    assert fetched.tags == ["backend", "acil"]


def test_default_priority_is_medium_and_tags_empty(db_conn):
    repo = TasksRepository(db_conn)
    created = repo.create(_task())

    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.priority == TaskPriority.medium
    assert fetched.tags == []


def test_update_changes_priority_and_tags(db_conn):
    repo = TasksRepository(db_conn)
    created = repo.create(_task())

    updated = repo.update(created.id, priority=TaskPriority.urgent, tags=["yeni-etiket"])
    assert updated is not None
    assert updated.priority == TaskPriority.urgent
    assert updated.tags == ["yeni-etiket"]


def test_checklist_progress_reflected_on_task(db_conn):
    repo = TasksRepository(db_conn)
    task = repo.create(_task())

    item1 = repo.add_checklist_item(task.id, "Wireframe")
    item2 = repo.add_checklist_item(task.id, "Renk paleti")

    fetched = repo.get(task.id)
    assert fetched is not None
    assert fetched.checklist_total == 2
    assert fetched.checklist_done == 0

    repo.set_checklist_item_done(item1.id, True)

    fetched_again = repo.get(task.id)
    assert fetched_again is not None
    assert fetched_again.checklist_done == 1

    items = repo.list_checklist_items(task.id)
    assert [i.title for i in items] == ["Wireframe", "Renk paleti"]
    assert items[0].done is True
    assert items[1].done is False

    repo.delete_checklist_item(item2.id)
    assert len(repo.list_checklist_items(task.id)) == 1


def test_task_with_no_checklist_items_has_zero_counts(db_conn):
    repo = TasksRepository(db_conn)
    task = repo.create(_task())

    fetched = repo.get(task.id)
    assert fetched is not None
    assert fetched.checklist_total == 0
    assert fetched.checklist_done == 0


def test_list_all_includes_checklist_counts_for_multiple_tasks(db_conn):
    repo = TasksRepository(db_conn)
    t1 = repo.create(_task(title="T1"))
    t2 = repo.create(_task(title="T2"))
    repo.add_checklist_item(t1.id, "a")
    repo.add_checklist_item(t1.id, "b")
    repo.add_checklist_item(t2.id, "c")

    all_tasks = {t.id: t for t in repo.list_all()}
    assert all_tasks[t1.id].checklist_total == 2
    assert all_tasks[t2.id].checklist_total == 1
