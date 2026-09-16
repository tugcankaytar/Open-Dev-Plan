"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from odp.api.routers import health
from odp.config import Settings, get_settings
from odp.db import open_db
from odp.jobs.gpu_lock import init_gpu_lock


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_dirs()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db = open_db(settings.db_path)
        init_gpu_lock(settings.gpu_concurrency)
        yield
        app.state.db.close()

    app = FastAPI(
        title="Open-Dev-Plan",
        description="Local-LLM powered work planning app.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router)

    return app
