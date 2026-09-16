"""Validates the JSON-schema-constrained + one-repair-pass contract
(plan §1/#4) using the FakeLLMProvider — no GPU/network needed."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from odp.services.llm import FakeLLMProvider, StructuredGenerationError, generate_structured


class ActionItem(BaseModel):
    title: str
    owner: str | None = None


async def test_generate_structured_happy_path():
    provider = FakeLLMProvider()
    provider.add_json_response("extract", {"title": "Demo hazırla", "owner": "alice"})

    result = await generate_structured(
        provider,
        prompt="extract the action item",
        schema_model=ActionItem,
        model="gpt-oss:20b",
    )
    assert result.title == "Demo hazırla"
    assert result.owner == "alice"


async def test_generate_structured_unmatched_prompt_raises():
    provider = FakeLLMProvider()
    with pytest.raises(LookupError):
        await generate_structured(
            provider,
            prompt="nothing registered",
            schema_model=ActionItem,
            model="gpt-oss:20b",
        )


async def test_generate_structured_surfaces_error_after_failed_repair(monkeypatch):
    provider = FakeLLMProvider()

    call_count = {"n": 0}

    async def always_invalid(**kwargs):
        call_count["n"] += 1
        return "not json"

    monkeypatch.setattr(provider, "generate_json", always_invalid)

    with pytest.raises(StructuredGenerationError) as exc_info:
        await generate_structured(
            provider,
            prompt="extract",
            schema_model=ActionItem,
            model="gpt-oss:20b",
        )
    assert call_count["n"] == 2  # one initial call + exactly one repair attempt
    assert exc_info.value.raw_response == "not json"
