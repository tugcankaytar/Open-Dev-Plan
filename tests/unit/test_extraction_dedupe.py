from __future__ import annotations

from odp.services.extraction.dedupe import (
    cosine_similarity,
    deduplicate_action_items,
    deduplicate_decisions,
)
from odp.services.extraction.schemas import ExtractedActionItem, ExtractedDecision
from odp.services.llm import FakeLLMProvider


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


async def test_deduplicate_action_items_merges_near_duplicates_and_fills_gaps():
    provider = FakeLLMProvider()
    # Two near-identical vectors (same task mentioned in two overlapping chunks).
    provider.add_embedding("Demo hazırla", [1.0, 0.0, 0.0])
    provider.add_embedding("demo hazırlansın", [0.99, 0.01, 0.0])
    provider.add_embedding("Bütçeyi güncelle", [0.0, 1.0, 0.0])

    items = [
        ExtractedActionItem(
            title="Demo hazırla", owner=None, source_quote="demo hazırla", confidence=0.7
        ),
        ExtractedActionItem(
            title="demo hazırlansın", owner="alice", source_quote="demo", confidence=0.9
        ),
        ExtractedActionItem(
            title="Bütçeyi güncelle", owner="bob", source_quote="bütçe", confidence=0.8
        ),
    ]

    result = await deduplicate_action_items(
        provider, items, embedding_model="bge-m3", threshold=0.85
    )

    assert len(result) == 2
    merged = next(i for i in result if i.title == "Demo hazırla")
    assert merged.owner == "alice"  # filled in from the duplicate
    assert merged.confidence == 0.9  # max of the two


async def test_deduplicate_action_items_short_circuits_for_zero_or_one_items():
    provider = FakeLLMProvider()  # no embeddings registered — would raise if called
    assert await deduplicate_action_items(provider, [], embedding_model="bge-m3") == []

    single = [ExtractedActionItem(title="X", source_quote="x", confidence=0.5)]
    result = await deduplicate_action_items(provider, single, embedding_model="bge-m3")
    assert result == single


async def test_deduplicate_decisions_merges_by_similarity():
    provider = FakeLLMProvider()
    provider.add_embedding("Bütçeyi onayladık", [1.0, 0.0])
    provider.add_embedding("bütçe onaylandı", [0.98, 0.02])

    items = [
        ExtractedDecision(summary="Bütçeyi onayladık", source_quote="q1", confidence=0.6),
        ExtractedDecision(summary="bütçe onaylandı", source_quote="q2", confidence=0.95),
    ]

    result = await deduplicate_decisions(provider, items, embedding_model="bge-m3", threshold=0.85)

    assert len(result) == 1
    assert result[0].confidence == 0.95
