"""CRUD for the `projects` table."""

from __future__ import annotations

import sqlite3

from odp.models import Project, ProjectStatus, new_id
from odp.models.time import utc_now_iso


class ProjectsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, name: str, description: str = "") -> Project:
        now = utc_now_iso()
        project = Project(
            id=new_id(), name=name, description=description, created_at=now, updated_at=now
        )
        self._conn.execute(
            "INSERT INTO projects (id, name, description, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project.id, project.name, project.description, project.status.value, now, now),
        )
        return project

    def get(self, project_id: str) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._row_to_project(row) if row else None

    def list(self, status: ProjectStatus | None = None) -> list[Project]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY created_at DESC", (status.value,)
            ).fetchall()
        return [self._row_to_project(row) for row in rows]

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: ProjectStatus | None = None,
    ) -> Project | None:
        existing = self.get(project_id)
        if existing is None:
            return None
        name = existing.name if name is None else name
        description = existing.description if description is None else description
        status = existing.status if status is None else status
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE projects SET name = ?, description = ?, status = ?, updated_at = ? "
            "WHERE id = ?",
            (name, description, status.value, now, project_id),
        )
        return self.get(project_id)

    def delete(self, project_id: str) -> None:
        self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=ProjectStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
