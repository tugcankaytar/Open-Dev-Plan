"""In-memory fake LLM provider for tests and CI.

Two modes:

- Scripted: pre-register exact responses keyed by a substring of the
  prompt (and, optionally, of the system prompt — needed because
  extraction's action-item and decision calls share an identical user
  prompt and differ only by system prompt), for unit tests that assert
  on specific behavior.
- Record/replay: capture real Ollama responses once (a small helper
  script under evals/), then replay them in CI with no GPU and no
  network — this is what plan §8 calls the VCR-style LLM test strategy.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from odp.services.llm.provider import ChatStreamEvent


@dataclass(frozen=True, slots=True)
class _ScriptedResponse:
    prompt_contains: str
    system_contains: str | None
    response: str


def _matches(scripted: _ScriptedResponse, prompt: str, system: str | None) -> bool:
    if scripted.prompt_contains not in prompt:
        return False
    if scripted.system_contains is None:
        return True
    return system is not None and scripted.system_contains in system


def _as_events(chunks: list[str | ChatStreamEvent]) -> list[ChatStreamEvent]:
    return [c if isinstance(c, ChatStreamEvent) else ChatStreamEvent(delta=c) for c in chunks]


@dataclass
class FakeLLMProvider:
    """Deterministic stand-in for OllamaProvider.

    Register responses with `add_json_response` / `add_text_response`
    before exercising code under test. Unmatched calls raise, so a test
    can't silently pass on real-but-unrouted behavior.
    """

    _json_responses: list[_ScriptedResponse] = field(default_factory=list)
    _text_responses: list[_ScriptedResponse] = field(default_factory=list)
    _stream_chat_responses: list[tuple[str, list[ChatStreamEvent]]] = field(default_factory=list)
    # Call-order-based script for multi-turn tool-calling loops, where a
    # later call's last message is a tool result, not user text — nothing
    # meaningful to content-match against. Consumed front-to-back,
    # independently of _stream_chat_responses.
    _stream_chat_sequence: list[list[ChatStreamEvent]] = field(default_factory=list)
    _embeddings: dict[str, list[float]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def add_json_response(
        self, prompt_contains: str, response: dict[str, Any], *, system_contains: str | None = None
    ) -> None:
        self._json_responses.append(
            _ScriptedResponse(prompt_contains, system_contains, json.dumps(response))
        )

    def add_text_response(
        self, prompt_contains: str, response: str, *, system_contains: str | None = None
    ) -> None:
        self._text_responses.append(_ScriptedResponse(prompt_contains, system_contains, response))

    def add_stream_chat_response(
        self, last_message_contains: str, chunks: list[str | ChatStreamEvent]
    ) -> None:
        self._stream_chat_responses.append((last_message_contains, _as_events(chunks)))

    def queue_stream_chat_call(self, events: list[str | ChatStreamEvent]) -> None:
        """Script the Nth call to stream_chat() by call order (N = however
        many are already queued), for tool-calling loop tests where later
        calls end on a tool-result message rather than user text."""
        self._stream_chat_sequence.append(_as_events(events))

    def add_embedding(self, text: str, vector: list[float]) -> None:
        self._embeddings[text] = vector

    async def generate_json(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
        model: str,
        system: str | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        self.calls.append({"kind": "json", "prompt": prompt, "model": model})
        for scripted in self._json_responses:
            if _matches(scripted, prompt, system):
                return scripted.response
        raise LookupError(
            f"FakeLLMProvider: no scripted JSON response matches prompt: {prompt[:200]!r}"
        )

    async def generate_text(
        self,
        *,
        prompt: str,
        model: str,
        system: str | None = None,
        temperature: float = 0.4,
    ) -> str:
        self.calls.append({"kind": "text", "prompt": prompt, "model": model})
        for scripted in self._text_responses:
            if _matches(scripted, prompt, system):
                return scripted.response
        raise LookupError(
            f"FakeLLMProvider: no scripted text response matches prompt: {prompt[:200]!r}"
        )

    async def stream_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.4,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        last_content = str(messages[-1].get("content", "")) if messages else ""
        self.calls.append({"kind": "stream_chat", "prompt": last_content, "model": model})

        if self._stream_chat_sequence:
            for event in self._stream_chat_sequence.pop(0):
                yield event
            return

        for prompt_contains, events in self._stream_chat_responses:
            if prompt_contains in last_content:
                for event in events:
                    yield event
                return
        raise LookupError(
            f"FakeLLMProvider: no scripted stream_chat response matches: {last_content[:200]!r}"
        )

    async def embed(self, *, text: str, model: str) -> list[float]:
        self.calls.append({"kind": "embed", "prompt": text, "model": model})
        if text in self._embeddings:
            return self._embeddings[text]
        raise LookupError(f"FakeLLMProvider: no scripted embedding for text: {text[:200]!r}")

    async def unload(self, model: str) -> None:
        self.calls.append({"kind": "unload", "model": model})
