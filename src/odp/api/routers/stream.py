"""Job status + SSE progress stream.

The UI enqueues a job (e.g. POST /api/meetings/{id}/extract) and gets a
`Job` id back immediately; it then opens this SSE stream to watch
progress without polling. The stream is a plain poll of the `jobs` table
under the hood (see jobs/worker.py's docstring for why that's the right
tradeoff — it's what makes jobs resumable across a restart).
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from odp.api.deps import get_db
from odp.models import Job, JobStatus
from odp.repositories.jobs import JobsRepository

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_TERMINAL = {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}
_POLL_INTERVAL_S = 0.5


@router.get("", response_model=list[Job])
def list_jobs(conn: sqlite3.Connection = Depends(get_db)) -> list[Job]:
    return JobsRepository(conn).list()


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str, conn: sqlite3.Connection = Depends(get_db)) -> Job:
    job = JobsRepository(conn).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: str, conn: sqlite3.Connection = Depends(get_db)) -> Job:
    repo = JobsRepository(conn)
    repo.cancel(job_id)
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, conn: sqlite3.Connection = Depends(get_db)) -> StreamingResponse:
    repo = JobsRepository(conn)
    if repo.get(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def event_source() -> AsyncIterator[str]:
        last_payload: str | None = None
        while True:
            job = repo.get(job_id)
            if job is None:
                return
            payload = job.model_dump_json()
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if job.status in _TERMINAL:
                return
            await asyncio.sleep(_POLL_INTERVAL_S)

    return StreamingResponse(event_source(), media_type="text/event-stream")
