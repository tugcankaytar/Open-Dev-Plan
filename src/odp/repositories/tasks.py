"""CRUD for `tasks` and `task_dependencies`."""

from __future__ import annotations

import sqlite3

from odp.models import DependencyType, Task, TaskDependency, TaskStatus, new_id
from odp.models.time import utc_now_iso


class TasksRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, task: Task) -> Task:
        now = utc_now_iso()
        task.created_at = now
        task.updated_at = now
        self._conn.execute(
            """
            INSERT INTO tasks
                (id, project_id, meeting_id, title, description, owner, due_utc, status,
                 source_segment_id, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.project_id,
                task.meeting_id,
                task.title,
                task.description,
                task.owner,
                task.due_utc,
                task.status.value,
                task.source_segment_id,
                task.confidence,
                task.created_at,
                task.updated_at,
            ),
        )
        return task

    def get(self, task_id: str) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_for_project(self, project_id: str) -> list[Task]:
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at ASC", (project_id,)
        ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def list_all(self) -> list[Task]:
        rows = self._conn.execute("SELECT * FROM tasks ORDER BY created_at ASC").fetchall()
        return [self._row_to_task(row) for row in rows]

    def update_status(self, task_id: str, status: TaskStatus) -> None:
        self._conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, utc_now_iso(), task_id),
        )

    def update(self, task_id: str, **fields: object) -> Task | None:
        existing = self.get(task_id)
        if existing is None:
            return None
        data = existing.model_dump()
        data.update(fields)
        merged = Task.model_validate(data)
        merged.updated_at = utc_now_iso()
        self._conn.execute(
            "UPDATE tasks SET title = ?, description = ?, owner = ?, due_utc = ?, status = ?, "
            "project_id = ?, updated_at = ? WHERE id = ?",
            (
                merged.title,
                merged.description,
                merged.owner,
                merged.due_utc,
                merged.status.value,
                merged.project_id,
                merged.updated_at,
                task_id,
            ),
        )
        return self.get(task_id)

    def delete(self, task_id: str) -> None:
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    # --- dependencies ---

    def add_dependency(
        self,
        task_id: str,
        depends_on_task_id: str,
        dep_type: DependencyType = DependencyType.finish_to_start,
    ) -> TaskDependency:
        dep = TaskDependency(
            id=new_id(), task_id=task_id, depends_on_task_id=depends_on_task_id, dep_type=dep_type
        )
        self._conn.execute(
            "INSERT INTO task_dependencies (id, task_id, depends_on_task_id, dep_type) "
            "VALUES (?, ?, ?, ?)",
            (dep.id, dep.task_id, dep.depends_on_task_id, dep.dep_type.value),
        )
        return dep

    def remove_dependency(self, dependency_id: str) -> None:
        self._conn.execute("DELETE FROM task_dependencies WHERE id = ?", (dependency_id,))

    def list_dependencies_for_project(self, project_id: str) -> list[TaskDependency]:
        rows = self._conn.execute(
            """
            SELECT td.* FROM task_dependencies td
            JOIN tasks t ON t.id = td.task_id
            WHERE t.project_id = ?
            """,
            (project_id,),
        ).fetchall()
        return [self._row_to_dependency(row) for row in rows]

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            project_id=row["project_id"],
            meeting_id=row["meeting_id"],
            title=row["title"],
            description=row["description"],
            owner=row["owner"],
            due_utc=row["due_utc"],
            status=TaskStatus(row["status"]),
            source_segment_id=row["source_segment_id"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_dependency(row: sqlite3.Row) -> TaskDependency:
        return TaskDependency(
            id=row["id"],
            task_id=row["task_id"],
            depends_on_task_id=row["depends_on_task_id"],
            dep_type=DependencyType(row["dep_type"]),
        )
