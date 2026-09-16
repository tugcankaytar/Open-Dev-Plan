"""Generate a fluent Turkish prose summary of a meeting.

Deliberately uses `generate_text` (free-form) and the *prose* model role
(plan §2), not the extraction model — this is the one output the user
reads directly, so Turkish fluency matters more than JSON-schema rigor
here.
"""

from __future__ import annotations

from odp.services.llm.provider import LLMProvider
from odp.services.prompts import PromptTemplate, load_prompt

SUMMARY_PROMPT: PromptTemplate = load_prompt("summary")


async def summarize_meeting(provider: LLMProvider, *, transcript_text: str, model: str) -> str:
    prompt = f"Toplantı transkripti:\n\n{transcript_text}"
    return await provider.generate_text(
        prompt=prompt,
        model=model,
        system=SUMMARY_PROMPT.text,
        temperature=0.4,
    )
