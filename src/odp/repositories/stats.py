"""Read-only aggregate queries for the dashboard (stat cards + charts).

Plain SQL, no LLM anywhere near it — a dashboard number should be exactly
reproducible from the data, same principle as the scheduler (plan §1/#1).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any

from odp.models import TaskStatus

TASK_STATUSES: list[TaskStatus] = [
    TaskStatus.todo,
    TaskStatus.in_progress,
    TaskStatus.blocked,
    TaskStatus.done,
]


class StatsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def dashboard_counts(self) -> dict[str, int]:
        projects = self._conn.execute(
            "SELECT COUNT(*) FROM projects WHERE status = 'active'"
        ).fetchone()[0]
        open_tasks = self._conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status != 'done'"
        ).fetchone()[0]
        overdue_tasks = self._conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status != 'done' "
            "AND due_utc IS NOT NULL AND due_utc < ?",
            (datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),),
        ).fetchone()[0]
        meetings = self._conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]
        pending_proposals = self._conn.execute(
            "SELECT COUNT(*) FROM proposals WHERE status = 'pending'"
        ).fetchone()[0]
        return {
            "active_projects": projects,
            "open_tasks": open_tasks,
            "overdue_tasks": overdue_tasks,
            "meetings": meetings,
            "pending_proposals": pending_proposals,
        }

    def task_status_counts(self) -> dict[str, int]:
        query = "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        rows = self._conn.execute(query).fetchall()
        counts = {row["status"]: row["n"] for row in rows}
        return {s.value: counts.get(s.value, 0) for s in TASK_STATUSES}

    def weekly_activity(self, *, days: int = 7) -> list[dict[str, Any]]:
        """Tasks created vs. completed per day for the last `days` days.

        "Completed" is approximated from `updated_at` on currently-done
        tasks — there's no status-change history table (yet), so a task
        edited again after completion would shift its counted day. Good
        enough for a trend chart, not an audit log.
        """
        today = datetime.now(UTC).date()
        start = today - timedelta(days=days - 1)

        created_rows = self._conn.execute(
            "SELECT date(created_at) AS d, COUNT(*) AS n FROM tasks WHERE date(created_at) >= ? "
            "GROUP BY d",
            (start.isoformat(),),
        ).fetchall()
        completed_rows = self._conn.execute(
            "SELECT date(updated_at) AS d, COUNT(*) AS n FROM tasks "
            "WHERE status = 'done' AND date(updated_at) >= ? GROUP BY d",
            (start.isoformat(),),
        ).fetchall()

        created_by_day = {row["d"]: row["n"] for row in created_rows}
        completed_by_day = {row["d"]: row["n"] for row in completed_rows}

        result = []
        for i in range(days):
            d: date = start + timedelta(days=i)
            key = d.isoformat()
            result.append(
                {
                    "date": key,
                    "created": created_by_day.get(key, 0),
                    "completed": completed_by_day.get(key, 0),
                }
            )
        return result
