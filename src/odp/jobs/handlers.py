"""Job handler registration: wires JobType -> the actual work function.

Kept separate from worker.py (generic dispatch loop) and from the
services themselves (pure logic, no notion of "a job") so each side
stays testable independently.
"""

from __future__ import annotations

import sqlite3

from odp.config import Settings
from odp.jobs.worker import ProgressCallback, Worker
from odp.models import Job, JobType
from odp.services.extraction.pipeline import extract_meeting
from odp.services.llm.provider import LLMProvider


def register_handlers(
    worker: Worker, conn: sqlite3.Connection, provider: LLMProvider, settings: Settings
) -> None:
    async def handle_extraction(job: Job, on_progress: ProgressCallback) -> None:
        meeting_id = job.payload["meeting_id"]
        await extract_meeting(
            conn,
            provider,
            meeting_id=meeting_id,
            extraction_model=settings.extraction_model,
            prose_model=settings.prose_model,
            embedding_model=settings.embedding_model,
        )

    worker.register(JobType.extraction, handle_extraction, needs_gpu=True)

    # Transcription (faster-whisper) and embedding (bge-m3, CPU) handlers
    # are registered once their services land — see plan slice 2 / slice 6.
    # Leaving them unregistered means a job of that type stays queued
    # rather than silently failing, which is the safer default.
