"""CRUD for the `projects` table.

A project can belong to zero or more customers (`project_customers`
join table) — a plain many-to-many, since a project is occasionally a
joint effort between clients or a mix of client + internal work.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from odp.models import Project, ProjectStatus, new_id
from odp.models.time import utc_now_iso

# Distinguishes "customer_ids not passed to update()" (keep existing
# links) from "customer_ids=[] passed explicitly" (clear all links) — a
# plain default of None can't tell those apart.
_UNSET: Any = object()


class ProjectsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self, name: str, description: str = "", customer_ids: list[str] | None = None
    ) -> Project:
        now = utc_now_iso()
        project = Project(
            id=new_id(),
            name=name,
            description=description,
            customer_ids=list(customer_ids or []),
            created_at=now,
            updated_at=now,
        )
        self._conn.execute(
            "INSERT INTO projects (id, name, description, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project.id, project.name, project.description, project.status.value, now, now),
        )
        self._set_customer_links(project.id, project.customer_ids)
        return project

    def get(self, project_id: str) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_project(row, self._customer_ids_for(project_id))

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: ProjectStatus | None = None,
        customer_ids: list[str] | None = _UNSET,
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
        if customer_ids is not _UNSET:
            self._set_customer_links(project_id, list(customer_ids or []))
        return self.get(project_id)

    def delete(self, project_id: str) -> None:
        self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def _set_customer_links(self, project_id: str, customer_ids: list[str]) -> None:
        self._conn.execute("DELETE FROM project_customers WHERE project_id = ?", (project_id,))
        if customer_ids:
            # dict.fromkeys dedupes while preserving the caller's order.
            self._conn.executemany(
                "INSERT INTO project_customers (project_id, customer_id) VALUES (?, ?)",
                [(project_id, cid) for cid in dict.fromkeys(customer_ids)],
            )

    def _customer_ids_for(self, project_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT customer_id FROM project_customers WHERE project_id = ?", (project_id,)
        ).fetchall()
        return [row["customer_id"] for row in rows]

    @staticmethod
    def _row_to_project(row: sqlite3.Row, customer_ids: list[str]) -> Project:
        return Project(
            id=row["id"],
            customer_ids=customer_ids,
            name=row["name"],
            description=row["description"],
            status=ProjectStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # Defined last: a method literally named `list` shadows the builtin
    # `list` name for every type annotation written after it in this
    # class body (a `from __future__ import annotations` + mypy quirk,
    # not a runtime issue) — keeping it last means every other method
    # above can use plain `list[str]` annotations safely.
    def list(
        self, status: ProjectStatus | None = None, customer_id: str | None = None
    ) -> list[Project]:
        query = "SELECT * FROM projects WHERE 1=1"
        params: list[str] = []
        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        if customer_id is not None:
            query += " AND id IN (SELECT project_id FROM project_customers WHERE customer_id = ?)"
            params.append(customer_id)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        if not rows:
            return []

        ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in ids)
        # ids is built purely from the length of `rows` above, never from
        # user-controlled SQL text — same pattern as get_segments_by_ids.
        link_rows = self._conn.execute(
            f"SELECT project_id, customer_id FROM project_customers "
            f"WHERE project_id IN ({placeholders})",
            ids,
        ).fetchall()
        customer_ids_by_project: dict[str, list[str]] = {}
        for link in link_rows:
            customer_ids_by_project.setdefault(link["project_id"], []).append(link["customer_id"])

        return [
            self._row_to_project(row, customer_ids_by_project.get(row["id"], [])) for row in rows
        ]
