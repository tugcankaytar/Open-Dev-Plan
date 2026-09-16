from __future__ import annotations

import asyncio

from odp.jobs.gpu_lock import init_gpu_lock
from odp.jobs.queue import JobQueue
from odp.jobs.worker import Worker
from odp.models import Job, JobStatus, JobType


async def test_worker_runs_a_queued_job_to_success(db_conn):
    init_gpu_lock(1)
    queue = JobQueue(db_conn)
    worker = Worker(db_conn, poll_interval_s=0.01)

    async def handler(job: Job, on_progress) -> None:
        on_progress(0.5)
        await asyncio.sleep(0)

    worker.register(JobType.transcription, handler, needs_gpu=True)

    job = queue.enqueue(JobType.transcription, {"meeting_id": "m1"})

    ran = await worker._run_one_available()
    assert ran is True

    result = queue.get(job.id)
    assert result is not None
    assert result.status == JobStatus.succeeded
    assert result.progress == 1.0


async def test_worker_marks_failed_job_with_error(db_conn):
    init_gpu_lock(1)
    queue = JobQueue(db_conn)
    worker = Worker(db_conn, poll_interval_s=0.01)

    async def failing_handler(job: Job, on_progress) -> None:
        raise ValueError("boom")

    worker.register(JobType.extraction, failing_handler, needs_gpu=False)
    job = queue.enqueue(JobType.extraction, {})

    await worker._run_one_available()

    result = queue.get(job.id)
    assert result is not None
    assert result.status == JobStatus.failed
    assert "boom" in (result.error or "")


async def test_cancel_prevents_future_claim(db_conn):
    queue = JobQueue(db_conn)
    job = queue.enqueue(JobType.briefing, {})
    queue.cancel(job.id)

    result = queue.get(job.id)
    assert result is not None
    assert result.status == JobStatus.cancelled
