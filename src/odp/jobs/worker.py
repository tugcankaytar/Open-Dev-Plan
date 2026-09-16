"""Background worker loop: claims queued jobs and dispatches to handlers.

Handlers are registered by job type and declare whether they need the GPU
slot (plan §4) — the embedding job (bge-m3 on CPU) intentionally does not,
so it can run concurrently with an LLM call.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from odp.jobs.gpu_lock import gpu_slot
from odp.models import Job, JobStatus, JobType
from odp.repositories.jobs import JobsRepository

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]
JobHandlerFn = Callable[[Job, ProgressCallback], Awaitable[None]]


@dataclass
class JobHandler:
    fn: JobHandlerFn
    needs_gpu: bool = True


class Worker:
    """Polls the `jobs` table and runs one job at a time per job type slot.

    A plain poll loop (not pub/sub) is deliberate: it's what makes jobs
    resumable across a process restart with zero extra state.
    """

    def __init__(self, conn: sqlite3.Connection, poll_interval_s: float = 0.5) -> None:
        self._conn = conn
        self._repo = JobsRepository(conn)
        self._handlers: dict[JobType, JobHandler] = {}
        self._poll_interval_s = poll_interval_s
        self._stop = asyncio.Event()

    def register(self, job_type: JobType, fn: JobHandlerFn, *, needs_gpu: bool = True) -> None:
        self._handlers[job_type] = JobHandler(fn=fn, needs_gpu=needs_gpu)

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            ran_one = await self._run_one_available()
            if not ran_one:
                await asyncio.sleep(self._poll_interval_s)

    async def _run_one_available(self) -> bool:
        for job_type, handler in self._handlers.items():
            job = self._repo.claim_next_queued(job_type)
            if job is None:
                continue
            await self._execute(job, handler)
            return True
        return False

    async def _execute(self, job: Job, handler: JobHandler) -> None:
        def on_progress(fraction: float) -> None:
            self._repo.update_progress(job.id, max(0.0, min(1.0, fraction)))

        try:
            if handler.needs_gpu:
                async with gpu_slot():
                    await handler.fn(job, on_progress)
            else:
                await handler.fn(job, on_progress)
            self._repo.mark_succeeded(job.id)
        except Exception as exc:
            logger.exception("job %s (%s) failed", job.id, job.job_type)
            self._repo.mark_failed(job.id, str(exc))
        finally:
            current = self._repo.get(job.id)
            if current is not None and current.status == JobStatus.running:
                # Defensive: a handler that returned without raising but also
                # without succeeding should not leave the job stuck "running".
                self._repo.mark_failed(job.id, "handler returned without completing")
