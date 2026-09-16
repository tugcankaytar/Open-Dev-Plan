"""Runtime model selection — the sidebar's model picker reads/writes here.

Separate from the process's `.env`-driven defaults (`odp.config.Settings`):
switching models from the UI writes to `app_settings` (see
repositories/app_settings.py) and takes effect on the next job/chat call,
no restart needed.
"""

from __future__ import annotations

import sqlite3

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from odp.api.deps import get_db, get_settings_dep
from odp.config import Settings
from odp.repositories.app_settings import AppSettingsRepository

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ModelSettingResponse(BaseModel):
    active_model: str
    available_models: list[str]


class ModelSettingUpdate(BaseModel):
    model: str


@router.get("/model", response_model=ModelSettingResponse)
async def get_model_setting(
    conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> ModelSettingResponse:
    active = AppSettingsRepository(conn).get_active_model(settings.extraction_model)
    available = await _list_ollama_models(settings.ollama_host)
    return ModelSettingResponse(active_model=active, available_models=available)


@router.put("/model", response_model=ModelSettingResponse)
async def set_model_setting(
    body: ModelSettingUpdate,
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> ModelSettingResponse:
    available = await _list_ollama_models(settings.ollama_host)
    if available and body.model not in available:
        raise HTTPException(
            status_code=422, detail=f"model {body.model!r} is not pulled in Ollama: {available}"
        )
    AppSettingsRepository(conn).set("active_model", body.model)
    return ModelSettingResponse(active_model=body.model, available_models=available)


async def _list_ollama_models(ollama_host: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    return sorted(m["name"] for m in data.get("models", []))
