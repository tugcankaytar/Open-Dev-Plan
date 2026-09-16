"""Durable job queue: enqueue/query/cancel API used by FastAPI routers.

The actual execution loop lives in worker.py. Splitting the two means API
handlers can enqueue and immediately return (the UI gets progress via SSE
against the `jobs` row) without needing a reference to the running worker.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from odp.models import Job, JobStatus, JobType
from odp.repositories.jobs import JobsRepository


class JobQueue:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._repo = JobsRepository(conn)

    def enqueue(self, job_type: JobType, payload: dict[str, Any]) -> Job:
        return self._repo.create(job_type, payload)

    def get(self, job_id: str) -> Job | None:
        return self._repo.get(job_id)

    def list(self, status: JobStatus | None = None) -> list[Job]:
        return self._repo.list(status)

    def cancel(self, job_id: str) -> None:
        self._repo.cancel(job_id)
