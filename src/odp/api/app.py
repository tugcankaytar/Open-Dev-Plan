"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from odp.api.routers import ai, calendar, health, meetings, projects, stream, tasks
from odp.config import Settings, get_settings
from odp.db import open_db
from odp.jobs.gpu_lock import init_gpu_lock
from odp.jobs.handlers import register_handlers
from odp.jobs.queue import JobQueue
from odp.jobs.worker import Worker
from odp.services.llm.ollama_provider import OllamaProvider


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_dirs()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db = open_db(settings.db_path)
        app.state.job_queue = JobQueue(app.state.db)
        app.state.llm_provider = OllamaProvider(
            settings.ollama_host, timeout_s=settings.llm_request_timeout_s
        )
        init_gpu_lock(settings.gpu_concurrency)

        worker = Worker(app.state.db)
        register_handlers(worker, app.state.db, app.state.llm_provider, settings)
        worker_task = asyncio.create_task(worker.run_forever())

        yield

        worker.stop()
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
        app.state.db.close()

    app = FastAPI(
        title="Open-Dev-Plan",
        description="Local-LLM powered work planning app.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    app.include_router(meetings.router)
    app.include_router(calendar.router)
    app.include_router(ai.router)
    app.include_router(stream.router)

    return app
