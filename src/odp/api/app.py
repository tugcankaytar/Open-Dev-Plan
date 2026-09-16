"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from odp.api.routers import (
    ai,
    calendar,
    chat,
    customers,
    health,
    meetings,
    projects,
    stats,
    stream,
    tasks,
)
from odp.api.routers import settings as settings_router
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
    app.include_router(customers.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    app.include_router(meetings.router)
    app.include_router(calendar.router)
    app.include_router(ai.router)
    app.include_router(stream.router)
    app.include_router(stats.router)
    app.include_router(chat.router)
    app.include_router(settings_router.router)

    # Serve the built frontend (npm run build in frontend/) if present, so
    # `uv run odp serve` alone is a complete app — no separate Node process
    # needed outside development. All /api/* routes above are registered
    # first and take precedence; this mount and the catch-all route below
    # only ever see what they don't match. Falls back to API-only
    # (frontend/dist absent) without error, e.g. in CI or a fresh checkout
    # before `npm run build` has run.
    #
    # TODO(packaging): once this ships via `uv tool install`, frontend/dist
    # needs to be included as package data (hatchling [tool.hatch.build]
    # force-include) so it's present outside a git checkout too.
    frontend_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount(
            "/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets"
        )
        index_path = frontend_dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            # Any other real file in dist/ (favicon, etc.) is served as-is;
            # everything else falls back to index.html so react-router's
            # client-side routes (e.g. a refresh on /tasks) work. Resolve
            # and re-check containment to reject a "../" path-traversal
            # attempt rather than serving a file outside frontend_dist.
            candidate = (frontend_dist / full_path).resolve()
            is_within_dist = candidate.is_relative_to(frontend_dist)
            if full_path and is_within_dist and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_path)

    return app
