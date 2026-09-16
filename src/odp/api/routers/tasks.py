from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from odp.api.deps import get_db
from odp.api.schemas import TaskCreate, TaskDependencyCreate, TaskUpdate
from odp.models import Task, TaskDependency
from odp.models.time import utc_now_iso
from odp.repositories.tasks import TasksRepository

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=Task, status_code=201)
def create_task(body: TaskCreate, conn: sqlite3.Connection = Depends(get_db)) -> Task:
    now = utc_now_iso()
    task = Task(
        title=body.title,
        description=body.description,
        owner=body.owner,
        due_utc=body.due_utc,
        project_id=body.project_id,
        meeting_id=body.meeting_id,
        created_at=now,
        updated_at=now,
    )
    return TasksRepository(conn).create(task)


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
    updated = TasksRepository(conn).update(task_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="task not found")
    return updated


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    TasksRepository(conn).delete(task_id)


@router.post("/{task_id}/dependencies", response_model=TaskDependency, status_code=201)
def add_dependency(
    task_id: str, body: TaskDependencyCreate, conn: sqlite3.Connection = Depends(get_db)
) -> TaskDependency:
    return TasksRepository(conn).add_dependency(task_id, body.depends_on_task_id, body.dep_type)


@router.delete("/dependencies/{dependency_id}", status_code=204)
def remove_dependency(dependency_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    TasksRepository(conn).remove_dependency(dependency_id)
