"""Ollama-backed LLMProvider implementation."""

from __future__ import annotations

from typing import Any

import ollama


class OllamaProvider:
    """Talks to a local `ollama serve` instance.

    Structured output uses Ollama's `format` parameter (constrained
    decoding against a JSON Schema) rather than parsing free text out of
    a prose response — see plan §1/#4.
    """

    def __init__(self, host: str, timeout_s: float = 120.0) -> None:
        self._client = ollama.AsyncClient(host=host, timeout=timeout_s)

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
        options: dict[str, Any] = {"temperature": temperature}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "format": json_schema,
            "options": options,
        }
        if reasoning_effort is not None:
            kwargs["think"] = reasoning_effort

        response = await self._client.chat(**kwargs)
        return str(response["message"]["content"])

    async def generate_text(
        self,
        *,
        prompt: str,
        model: str,
        system: str | None = None,
        temperature: float = 0.4,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature},
        )
        return str(response["message"]["content"])

    async def embed(self, *, text: str, model: str) -> list[float]:
        response = await self._client.embed(model=model, input=text)
        return list(response["embeddings"][0])

    async def unload(self, model: str) -> None:
        # keep_alive=0 tells Ollama to evict the model from VRAM right away.
        await self._client.generate(model=model, prompt="", keep_alive=0)
