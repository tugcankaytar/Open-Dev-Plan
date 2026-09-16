from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from odp.api.deps import get_db
from odp.api.schemas import ProjectCreate, ProjectUpdate
from odp.models import Project
from odp.repositories.projects import ProjectsRepository

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=201)
def create_project(body: ProjectCreate, conn: sqlite3.Connection = Depends(get_db)) -> Project:
    return ProjectsRepository(conn).create(body.name, body.description)


@router.get("", response_model=list[Project])
def list_projects(conn: sqlite3.Connection = Depends(get_db)) -> list[Project]:
    return ProjectsRepository(conn).list()


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
    updated = ProjectsRepository(conn).update(
        project_id, name=body.name, description=body.description, status=body.status
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="project not found")
    return updated


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    ProjectsRepository(conn).delete(project_id)
