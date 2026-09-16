"""Extract decisions from a transcript excerpt."""

from __future__ import annotations

from odp.services.extraction.schemas import DecisionsExtraction
from odp.services.llm.provider import LLMProvider
from odp.services.llm.structured import generate_structured
from odp.services.prompts import PromptTemplate, load_prompt

DECISIONS_PROMPT: PromptTemplate = load_prompt("decisions")


async def extract_decisions(
    provider: LLMProvider, *, transcript_text: str, model: str
) -> DecisionsExtraction:
    prompt = f"Toplantı transkripti:\n\n{transcript_text}"
    return await generate_structured(
        provider,
        prompt=prompt,
        schema_model=DecisionsExtraction,
        model=model,
        system=DECISIONS_PROMPT.text,
        reasoning_effort="medium",
    )
