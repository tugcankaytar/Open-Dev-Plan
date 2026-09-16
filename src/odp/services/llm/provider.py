"""LLM provider abstraction.

Everything that talks to a model goes through this ``Protocol`` (plan §4).
Two reasons, not one:

1. Swappability — Ollama today, something else tomorrow, without touching
   callers.
2. Testability — ``FakeLLMProvider`` (see fake_provider.py) lets the whole
   extraction/scheduling pipeline run in CI with no GPU and no network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal surface every LLM backend must implement."""

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
        """Generate a response constrained to the given JSON Schema.

        Returns the raw JSON string (not yet parsed/validated — that's
        structured.py's job, since retry-on-invalid needs the raw text).
        """
        ...

    async def generate_text(
        self,
        *,
        prompt: str,
        model: str,
        system: str | None = None,
        temperature: float = 0.4,
    ) -> str:
        """Generate free-form prose (summaries, briefs) — no schema."""
        ...

    def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.4,
    ) -> AsyncIterator[str]:
        """Stream a multi-turn chat reply as text deltas (the chat panel's
        backend). `messages` is `[{"role": "system"|"user"|"assistant",
        "content": ...}, ...]`, ending on the newest user turn.
        """
        ...

    async def embed(self, *, text: str, model: str) -> list[float]:
        """Return a dense embedding vector for the given text."""
        ...

    async def unload(self, model: str) -> None:
        """Release a model's VRAM immediately (keep_alive=0).

        Called before handing the GPU to another workload (Whisper, LoRA
        training) — see the GPU semaphore in jobs/gpu_lock.py and plan §4.
        """
        ...
