"""Merge near-duplicate action items found across overlapping transcript
chunks (plan §6 step 3). Similarity is embedding cosine distance, not
another LLM judgment call — cheap, deterministic given the embeddings,
and good enough for "is this the same task mentioned twice."
"""

from __future__ import annotations

import math

from odp.services.extraction.schemas import ExtractedActionItem, ExtractedDecision
from odp.services.llm.provider import LLMProvider

DEFAULT_SIMILARITY_THRESHOLD = 0.85


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _merge(primary: ExtractedActionItem, other: ExtractedActionItem) -> ExtractedActionItem:
    """Combine two duplicate detections, preferring whichever has more info."""
    return primary.model_copy(
        update={
            "owner": primary.owner or other.owner,
            "due_day_of_week": primary.due_day_of_week or other.due_day_of_week,
            "due_explicit_date": primary.due_explicit_date or other.due_explicit_date,
            "confidence": max(primary.confidence, other.confidence),
        }
    )


async def deduplicate_action_items(
    provider: LLMProvider,
    items: list[ExtractedActionItem],
    *,
    embedding_model: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[ExtractedActionItem]:
    if len(items) <= 1:
        return list(items)

    kept: list[ExtractedActionItem] = []
    kept_embeddings: list[list[float]] = []

    for item in items:
        embedding = await provider.embed(text=item.title, model=embedding_model)
        merged_into_existing = False
        for i, existing_embedding in enumerate(kept_embeddings):
            if cosine_similarity(embedding, existing_embedding) >= threshold:
                kept[i] = _merge(kept[i], item)
                merged_into_existing = True
                break
        if not merged_into_existing:
            kept.append(item)
            kept_embeddings.append(embedding)

    return kept


async def deduplicate_decisions(
    provider: LLMProvider,
    items: list[ExtractedDecision],
    *,
    embedding_model: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[ExtractedDecision]:
    if len(items) <= 1:
        return list(items)

    kept: list[ExtractedDecision] = []
    kept_embeddings: list[list[float]] = []

    for item in items:
        embedding = await provider.embed(text=item.summary, model=embedding_model)
        merged_into_existing = False
        for i, existing_embedding in enumerate(kept_embeddings):
            if cosine_similarity(embedding, existing_embedding) >= threshold:
                kept[i] = kept[i].model_copy(
                    update={"confidence": max(kept[i].confidence, item.confidence)}
                )
                merged_into_existing = True
                break
        if not merged_into_existing:
            kept.append(item)
            kept_embeddings.append(embedding)

    return kept
