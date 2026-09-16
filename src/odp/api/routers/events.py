"""Live-update stream: one SSE connection per open browser tab, told
whenever any write happens anywhere in the app (a REST call, a chat tool
call, a background job finishing) — this is what lets the frontend never
need a manual page reload.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from odp.services import events

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def stream_events() -> StreamingResponse:
    async def event_source() -> AsyncIterator[str]:
        async for scope in events.subscribe():
            yield f"data: {scope}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
