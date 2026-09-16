"""CRUD for the `jobs` table.

Jobs are durable: a row exists from the moment work is enqueued until it
finishes, so a process restart doesn't lose track of in-flight
transcription/extraction/embedding/briefing work (plan §4).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from odp.models import Job, JobStatus, JobType, new_id
from odp.models.time import utc_now_iso


class JobsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, job_type: JobType, payload: dict[str, Any]) -> Job:
        now = utc_now_iso()
        job = Job(id=new_id(), job_type=job_type, payload=payload, created_at=now, updated_at=now)
        self._conn.execute(
            """
            INSERT INTO jobs (id, job_type, status, payload_json, progress, error,
                               created_at, updated_at, started_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.job_type.value,
                job.status.value,
                json.dumps(job.payload),
                job.progress,
                job.error,
                job.created_at,
                job.updated_at,
                job.started_at,
                job.finished_at,
            ),
        )
        return job

    def get(self, job_id: str) -> Job | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list(self, status: JobStatus | None = None) -> list[Job]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC", (status.value,)
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def claim_next_queued(self, job_type: JobType | None = None) -> Job | None:
        """Atomically claim the oldest queued job (optionally of one type)."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            if job_type is None:
                row = self._conn.execute(
                    "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT * FROM jobs WHERE status = 'queued' AND job_type = ? "
                    "ORDER BY created_at ASC LIMIT 1",
                    (job_type.value,),
                ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return None
            job = self._row_to_job(row)
            now = utc_now_iso()
            self._conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ?, updated_at = ? WHERE id = ?",
                (now, now, job.id),
            )
            self._conn.execute("COMMIT")
            job.status = JobStatus.running
            job.started_at = now
            job.updated_at = now
            return job
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def update_progress(self, job_id: str, progress: float) -> None:
        self._conn.execute(
            "UPDATE jobs SET progress = ?, updated_at = ? WHERE id = ?",
            (progress, utc_now_iso(), job_id),
        )

    def mark_succeeded(self, job_id: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE jobs SET status = 'succeeded', progress = 1.0, "
            "finished_at = ?, updated_at = ? WHERE id = ?",
            (now, now, job_id),
        )

    def mark_failed(self, job_id: str, error: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE jobs SET status = 'failed', error = ?, finished_at = ?, updated_at = ? "
            "WHERE id = ?",
            (error, now, now, job_id),
        )

    def cancel(self, job_id: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE jobs SET status = 'cancelled', finished_at = ?, updated_at = ? "
            "WHERE id = ? AND status IN ('queued', 'running')",
            (now, now, job_id),
        )

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            job_type=JobType(row["job_type"]),
            status=JobStatus(row["status"]),
            payload=json.loads(row["payload_json"]),
            progress=row["progress"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )
