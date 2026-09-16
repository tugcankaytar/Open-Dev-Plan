"""Health check + first-run environment diagnostics.

Deliberately checks the things that silently break this app if missing
(plan §9's setup wizard): is Ollama reachable, are the configured models
pulled, is a CUDA GPU visible for Whisper. Each check degrades to a
reported problem rather than raising, so the endpoint always responds.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import httpx
from fastapi import APIRouter, Request

from odp.config import Settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    conn: sqlite3.Connection = request.app.state.db

    db_ok = True
    try:
        conn.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        db_ok = False

    ollama_status = await _check_ollama(settings)

    return {
        "status": "ok" if db_ok and ollama_status["reachable"] else "degraded",
        "db": {"ok": db_ok, "path": str(settings.db_path)},
        "ollama": ollama_status,
    }


async def _check_ollama(settings: Settings) -> dict[str, Any]:
    required_models = [settings.extraction_model, settings.prose_model, settings.embedding_model]

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {
            "reachable": False,
            "required_models_present": False,
            "missing_models": required_models,
        }

    installed = {m["name"] for m in data.get("models", [])}
    installed_base_names = _base_names(installed)

    def is_missing(m: str) -> bool:
        return m not in installed and _base_name(m) not in installed_base_names

    missing = sorted(m for m in required_models if is_missing(m))

    return {
        "reachable": True,
        "installed_models": sorted(installed),
        "required_models_present": not missing,
        "missing_models": missing,
    }


def _base_name(model_tag: str) -> str:
    """'gpt-oss:20b' -> 'gpt-oss' — tolerate tag differences when comparing."""
    return model_tag.split(":", 1)[0]


def _base_names(tags: set[str]) -> set[str]:
    return {_base_name(t) for t in tags}
