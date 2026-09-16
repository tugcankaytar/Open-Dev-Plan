from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from odp.api.deps import get_db
from odp.api.schemas import ProjectCreate, ProjectUpdate
from odp.models import Project
from odp.repositories.projects import ProjectsRepository
from odp.services import events

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=201)
def create_project(body: ProjectCreate, conn: sqlite3.Connection = Depends(get_db)) -> Project:
    project = ProjectsRepository(conn).create(body.name, body.description, body.customer_id)
    events.publish("projects")
    return project


@router.get("", response_model=list[Project])
def list_projects(
    customer_id: str | None = Query(default=None), conn: sqlite3.Connection = Depends(get_db)
) -> list[Project]:
    return ProjectsRepository(conn).list(customer_id=customer_id)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, conn: sqlite3.Connection = Depends(get_db)) -> Project:
    project = ProjectsRepository(conn).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.patch("/{project_id}", response_model=Project)
def update_project(
    project_id: str, body: ProjectUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> Project:
    # exclude_unset: a field the client never sent must NOT overwrite the
    # existing value — matters most for customer_id, where "not sent" and
    # "explicitly cleared" (null) are different requests.
    fields = body.model_dump(exclude_unset=True)
    updated = ProjectsRepository(conn).update(project_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="project not found")
    events.publish("projects")
    return updated


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    ProjectsRepository(conn).delete(project_id)
    events.publish("projects")
