"""FastAPI dependency accessors — thin wrappers around `request.app.state`
set up once in the lifespan (api/app.py)."""

from __future__ import annotations

import sqlite3

from fastapi import Request

from odp.config import Settings
from odp.jobs.queue import JobQueue
from odp.services.llm.provider import LLMProvider


def get_db(request: Request) -> sqlite3.Connection:
    return request.app.state.db  # type: ignore[no-any-return]


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_llm_provider(request: Request) -> LLMProvider:
    return request.app.state.llm_provider  # type: ignore[no-any-return]


def get_job_queue(request: Request) -> JobQueue:
    return request.app.state.job_queue  # type: ignore[no-any-return]
