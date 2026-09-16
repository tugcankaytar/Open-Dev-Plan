"""CRUD for the `projects` table."""

from __future__ import annotations

import sqlite3
from typing import Any

from odp.models import Project, ProjectStatus, new_id
from odp.models.time import utc_now_iso

# Distinguishes "customer_id not passed to update()" (keep existing value)
# from "customer_id=None passed explicitly" (clear the customer link) —
# a plain default of None can't tell those apart.
_UNSET: Any = object()


class ProjectsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, name: str, description: str = "", customer_id: str | None = None) -> Project:
        now = utc_now_iso()
        project = Project(
            id=new_id(),
            name=name,
            description=description,
            customer_id=customer_id,
            created_at=now,
            updated_at=now,
        )
        self._conn.execute(
            "INSERT INTO projects "
            "(id, name, description, customer_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                project.id,
                project.name,
                project.description,
                customer_id,
                project.status.value,
                now,
                now,
            ),
        )
        return project

    def get(self, project_id: str) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._row_to_project(row) if row else None

    def list(
        self, status: ProjectStatus | None = None, customer_id: str | None = None
    ) -> list[Project]:
        query = "SELECT * FROM projects WHERE 1=1"
        params: list[str] = []
        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        if customer_id is not None:
            query += " AND customer_id = ?"
            params.append(customer_id)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_project(row) for row in rows]

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: ProjectStatus | None = None,
        customer_id: str | None = _UNSET,
    ) -> Project | None:
        existing = self.get(project_id)
        if existing is None:
            return None
        name = existing.name if name is None else name
        description = existing.description if description is None else description
        status = existing.status if status is None else status
        customer_id = existing.customer_id if customer_id is _UNSET else customer_id
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE projects SET name = ?, description = ?, status = ?, customer_id = ?, "
            "updated_at = ? WHERE id = ?",
            (name, description, status.value, customer_id, now, project_id),
        )
        return self.get(project_id)

    def delete(self, project_id: str) -> None:
        self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            customer_id=row["customer_id"],
            name=row["name"],
            description=row["description"],
            status=ProjectStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
