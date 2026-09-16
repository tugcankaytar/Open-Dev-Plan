from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from odp.api.deps import get_db
from odp.api.schemas import (
    ChecklistItemCreate,
    ChecklistItemUpdate,
    TaskCreate,
    TaskDependencyCreate,
    TaskUpdate,
)
from odp.models import ChecklistItem, Task, TaskDependency
from odp.models.time import normalize_utc_iso, utc_now_iso
from odp.repositories.tasks import TasksRepository
from odp.services import events

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=Task, status_code=201)
def create_task(body: TaskCreate, conn: sqlite3.Connection = Depends(get_db)) -> Task:
    now = utc_now_iso()
    task = Task(
        title=body.title,
        description=body.description,
        owner=body.owner,
        # Client-supplied timestamps (the browser's `Date.toISOString()`
        # always carries milliseconds) are reserialized to our canonical
        # no-fractional-seconds form before storage — see normalize_utc_iso.
        due_utc=normalize_utc_iso(body.due_utc) if body.due_utc else None,
        start_utc=normalize_utc_iso(body.start_utc) if body.start_utc else None,
        priority=body.priority,
        tags=body.tags,
        project_id=body.project_id,
        meeting_id=body.meeting_id,
        created_at=now,
        updated_at=now,
    )
    created = TasksRepository(conn).create(task)
    events.publish("tasks")
    return created


@router.get("", response_model=list[Task])
def list_tasks(
    project_id: str | None = Query(default=None), conn: sqlite3.Connection = Depends(get_db)
) -> list[Task]:
    repo = TasksRepository(conn)
    return repo.list_for_project(project_id) if project_id else repo.list_all()


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str, conn: sqlite3.Connection = Depends(get_db)) -> Task:
    task = TasksRepository(conn).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: str, body: TaskUpdate, conn: sqlite3.Connection = Depends(get_db)) -> Task:
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if fields.get("due_utc"):
        fields["due_utc"] = normalize_utc_iso(fields["due_utc"])
    if fields.get("start_utc"):
        fields["start_utc"] = normalize_utc_iso(fields["start_utc"])
    updated = TasksRepository(conn).update(task_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="task not found")
    events.publish("tasks")
    return updated


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    TasksRepository(conn).delete(task_id)
    events.publish("tasks")


@router.post("/{task_id}/dependencies", response_model=TaskDependency, status_code=201)
def add_dependency(
    task_id: str, body: TaskDependencyCreate, conn: sqlite3.Connection = Depends(get_db)
) -> TaskDependency:
    dep = TasksRepository(conn).add_dependency(task_id, body.depends_on_task_id, body.dep_type)
    events.publish("tasks")
    return dep


@router.delete("/dependencies/{dependency_id}", status_code=204)
def remove_dependency(dependency_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    TasksRepository(conn).remove_dependency(dependency_id)
    events.publish("tasks")


# --- checklist ---


@router.get("/{task_id}/checklist", response_model=list[ChecklistItem])
def list_checklist(task_id: str, conn: sqlite3.Connection = Depends(get_db)) -> list[ChecklistItem]:
    return TasksRepository(conn).list_checklist_items(task_id)


@router.post("/{task_id}/checklist", response_model=ChecklistItem, status_code=201)
def add_checklist_item(
    task_id: str, body: ChecklistItemCreate, conn: sqlite3.Connection = Depends(get_db)
) -> ChecklistItem:
    item = TasksRepository(conn).add_checklist_item(task_id, body.title)
    events.publish("tasks")
    return item


@router.patch("/checklist/{item_id}", status_code=204)
def update_checklist_item(
    item_id: str, body: ChecklistItemUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> None:
    TasksRepository(conn).set_checklist_item_done(item_id, body.done)
    events.publish("tasks")


@router.delete("/checklist/{item_id}", status_code=204)
def delete_checklist_item(item_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    TasksRepository(conn).delete_checklist_item(item_id)
    events.publish("tasks")
