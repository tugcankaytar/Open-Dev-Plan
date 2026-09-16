"""Chat panel backend: context + history -> streamed reply, with the
assistant able to call a small set of write tools directly (see
services/chat/tools.py for the tool set and why direct execution is a
deliberate, scoped exception to the "AI proposes, human disposes" rule
the rest of the app follows).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel

from odp.services.chat.context import build_context
from odp.services.chat.tools import TOOL_SCHEMAS, execute_tool
from odp.services.llm.provider import LLMProvider, ToolCallRequest
from odp.services.prompts import load_prompt

CHAT_PROMPT = load_prompt("chat_assistant")

# Keep only the last few turns in the prompt — this is a context-window
# budget choice, not a UX one: the app-data snapshot already costs a few
# hundred to a couple thousand tokens, and older turns matter far less
# than fresh data (plan §6's token-budget discipline applies here too).
MAX_HISTORY_TURNS = 8

# A tool call's result feeds back into another model turn, which might
# itself call another tool (e.g. create a task, then add a checklist item
# to it) — bounded so a confused model can't loop forever.
MAX_TOOL_ROUNDS = 4


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatEvent(BaseModel):
    """One emitted unit of a chat reply — the API layer serializes these
    straight to SSE. Exactly one of the three fields is set per event."""

    delta: str | None = None
    tool_call: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None


def _tool_calls_to_message(tool_calls: list[ToolCallRequest]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": tc.name, "arguments": tc.arguments}} for tc in tool_calls
        ],
    }


async def stream_chat_reply(
    conn: sqlite3.Connection,
    provider: LLMProvider,
    *,
    message: str,
    history: list[ChatTurn],
    model: str,
    timezone: str = "UTC",
) -> AsyncIterator[ChatEvent]:
    context = build_context(conn, timezone=timezone)
    system = f"{CHAT_PROMPT.text}\n\n---\n\n{context}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for turn in history[-MAX_HISTORY_TURNS:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": message})

    for _round in range(MAX_TOOL_ROUNDS):
        collected_tool_calls: list[ToolCallRequest] = []
        async for event in provider.stream_chat(
            messages=messages, model=model, temperature=0.4, tools=TOOL_SCHEMAS
        ):
            if event.delta:
                yield ChatEvent(delta=event.delta)
            if event.tool_calls:
                collected_tool_calls.extend(event.tool_calls)

        if not collected_tool_calls:
            return  # the model answered in plain text — done

        messages.append(_tool_calls_to_message(collected_tool_calls))
        for tc in collected_tool_calls:
            yield ChatEvent(tool_call={"name": tc.name, "arguments": tc.arguments})
            result = execute_tool(conn, tc.name, tc.arguments, timezone=timezone)
            yield ChatEvent(tool_result={"name": tc.name, **result})
            messages.append(
                {
                    "role": "tool",
                    "tool_name": tc.name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        # loop: give the model another turn to either report back in text
        # or chain a further tool call (e.g. create a task, then tag it)

    yield ChatEvent(delta="\n\n_(Çok fazla işlem adımı denendi, son cevabı tamamlayamadım.)_")
