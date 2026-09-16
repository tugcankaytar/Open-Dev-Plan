"""CRUD for `tasks`, `task_dependencies`, and `task_checklist_items`."""

from __future__ import annotations

import json
import sqlite3

from odp.models import (
    ChecklistItem,
    DependencyType,
    Task,
    TaskDependency,
    TaskPriority,
    TaskStatus,
    new_id,
)
from odp.models.time import utc_now_iso

# Checklist progress ("2/5") is computed with every task read via this
# join, not fetched per-task — avoids an N+1 query pattern when rendering
# a Kanban board full of cards.
_SELECT_TASK = """
    SELECT t.*,
           COALESCE(c.total, 0) AS checklist_total,
           COALESCE(c.done, 0) AS checklist_done
    FROM tasks t
    LEFT JOIN (
        SELECT task_id, COUNT(*) AS total, SUM(done) AS done
        FROM task_checklist_items
        GROUP BY task_id
    ) c ON c.task_id = t.id
"""


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
                (id, project_id, meeting_id, title, description, owner, due_utc, start_utc,
                 priority, tags_json, status, source_segment_id, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.project_id,
                task.meeting_id,
                task.title,
                task.description,
                task.owner,
                task.due_utc,
                task.start_utc,
                task.priority.value,
                json.dumps(task.tags),
                task.status.value,
                task.source_segment_id,
                task.confidence,
                task.created_at,
                task.updated_at,
            ),
        )
        return task

    def get(self, task_id: str) -> Task | None:
        row = self._conn.execute(f"{_SELECT_TASK} WHERE t.id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_for_project(self, project_id: str) -> list[Task]:
        rows = self._conn.execute(
            f"{_SELECT_TASK} WHERE t.project_id = ? ORDER BY t.created_at ASC", (project_id,)
        ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def list_all(self) -> list[Task]:
        rows = self._conn.execute(f"{_SELECT_TASK} ORDER BY t.created_at ASC").fetchall()
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
            "UPDATE tasks SET title = ?, description = ?, owner = ?, due_utc = ?, start_utc = ?, "
            "priority = ?, tags_json = ?, status = ?, project_id = ?, updated_at = ? WHERE id = ?",
            (
                merged.title,
                merged.description,
                merged.owner,
                merged.due_utc,
                merged.start_utc,
                merged.priority.value,
                json.dumps(merged.tags),
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

    # --- checklist items ---

    def add_checklist_item(self, task_id: str, title: str) -> ChecklistItem:
        next_seq_row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM task_checklist_items WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        item = ChecklistItem(
            id=new_id(), task_id=task_id, title=title, seq=next_seq_row[0], created_at=utc_now_iso()
        )
        self._conn.execute(
            "INSERT INTO task_checklist_items (id, task_id, title, done, seq, created_at) "
            "VALUES (?, ?, ?, 0, ?, ?)",
            (item.id, item.task_id, item.title, item.seq, item.created_at),
        )
        return item

    def list_checklist_items(self, task_id: str) -> list[ChecklistItem]:
        rows = self._conn.execute(
            "SELECT * FROM task_checklist_items WHERE task_id = ? ORDER BY seq ASC", (task_id,)
        ).fetchall()
        return [self._row_to_checklist_item(row) for row in rows]

    def set_checklist_item_done(self, item_id: str, done: bool) -> None:
        self._conn.execute(
            "UPDATE task_checklist_items SET done = ? WHERE id = ?", (1 if done else 0, item_id)
        )

    def delete_checklist_item(self, item_id: str) -> None:
        self._conn.execute("DELETE FROM task_checklist_items WHERE id = ?", (item_id,))

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
            start_utc=row["start_utc"],
            priority=TaskPriority(row["priority"]),
            tags=json.loads(row["tags_json"]),
            status=TaskStatus(row["status"]),
            source_segment_id=row["source_segment_id"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            checklist_total=row["checklist_total"],
            checklist_done=row["checklist_done"],
        )

    @staticmethod
    def _row_to_dependency(row: sqlite3.Row) -> TaskDependency:
        return TaskDependency(
            id=row["id"],
            task_id=row["task_id"],
            depends_on_task_id=row["depends_on_task_id"],
            dep_type=DependencyType(row["dep_type"]),
        )

    @staticmethod
    def _row_to_checklist_item(row: sqlite3.Row) -> ChecklistItem:
        return ChecklistItem(
            id=row["id"],
            task_id=row["task_id"],
            title=row["title"],
            done=bool(row["done"]),
            seq=row["seq"],
            created_at=row["created_at"],
        )
