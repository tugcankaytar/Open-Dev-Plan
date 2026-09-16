"""Extract action items from a transcript excerpt."""

from __future__ import annotations

from odp.services.extraction.schemas import ActionItemsExtraction
from odp.services.llm.provider import LLMProvider
from odp.services.llm.structured import generate_structured
from odp.services.prompts import PromptTemplate, load_prompt

ACTION_ITEMS_PROMPT: PromptTemplate = load_prompt("action_items")


async def extract_action_items(
    provider: LLMProvider, *, transcript_text: str, model: str
) -> ActionItemsExtraction:
    prompt = f"Toplantı transkripti:\n\n{transcript_text}"
    return await generate_structured(
        provider,
        prompt=prompt,
        schema_model=ActionItemsExtraction,
        model=model,
        system=ACTION_ITEMS_PROMPT.text,
        reasoning_effort="medium",
    )
