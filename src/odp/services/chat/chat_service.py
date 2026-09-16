"""Chat panel backend: context + history -> streamed reply."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel

from odp.services.chat.context import build_context
from odp.services.llm.provider import LLMProvider
from odp.services.prompts import load_prompt

CHAT_PROMPT = load_prompt("chat_assistant")

# Keep only the last few turns in the prompt — this is a context-window
# budget choice, not a UX one: the app-data snapshot already costs a few
# hundred to a couple thousand tokens, and older turns matter far less
# than fresh data (plan §6's token-budget discipline applies here too).
MAX_HISTORY_TURNS = 8


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


async def stream_chat_reply(
    conn: sqlite3.Connection,
    provider: LLMProvider,
    *,
    message: str,
    history: list[ChatTurn],
    model: str,
    timezone: str = "UTC",
) -> AsyncIterator[str]:
    context = build_context(conn, timezone=timezone)
    system = f"{CHAT_PROMPT.text}\n\n---\n\n{context}"

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for turn in history[-MAX_HISTORY_TURNS:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": message})

    async for delta in provider.stream_chat(messages=messages, model=model, temperature=0.4):
        yield delta
