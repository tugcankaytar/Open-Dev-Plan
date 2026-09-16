"""The chat panel's backend: POST, stream back.

Not GET+EventSource (job progress's pattern) because the payload — the
message plus conversation history — belongs in a request body, and
EventSource only issues GET. The frontend instead reads the POST
response body as a stream via `fetch()` + a `ReadableStream` reader,
parsing the same `data: {...}\\n\\n` shape by hand.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from odp.api.deps import get_db, get_llm_provider, get_settings_dep
from odp.api.schemas import ChatRequest
from odp.config import Settings
from odp.repositories.app_settings import AppSettingsRepository
from odp.services.chat import ChatTurn, stream_chat_reply
from odp.services.llm.provider import LLMProvider

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(
    body: ChatRequest,
    conn: sqlite3.Connection = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings_dep),
) -> StreamingResponse:
    model = AppSettingsRepository(conn).get_active_model(settings.extraction_model)
    history = [ChatTurn(role=t.role, content=t.content) for t in body.history]

    async def event_source() -> AsyncIterator[str]:
        try:
            async for event in stream_chat_reply(
                conn,
                provider,
                message=body.message,
                history=history,
                model=model,
                timezone=settings.default_timezone,
            ):
                yield f"data: {event.model_dump_json(exclude_none=True)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            # Surface any failure to the chat UI as a message rather than a
            # silently truncated stream.
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
