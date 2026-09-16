"""Unit tests for the three single-purpose extractors, each in isolation
via FakeLLMProvider. Pipeline-level wiring (chunking + dedupe + proposal
persistence) is covered in tests/integration/test_extraction_pipeline.py.
"""

from __future__ import annotations

from odp.services.extraction.actions import extract_action_items
from odp.services.extraction.decisions import extract_decisions
from odp.services.extraction.summarize import summarize_meeting
from odp.services.llm import FakeLLMProvider

TRANSCRIPT = "[Ayşe] Demo hazırlığını Cuma'ya kadar bitirelim mi? [Mehmet] Tamam, ben hazırlarım."


async def test_extract_action_items_returns_validated_schema():
    provider = FakeLLMProvider()
    provider.add_json_response(
        "Demo hazırlığını",
        {
            "action_items": [
                {
                    "title": "Demo hazırlığını bitir",
                    "owner": "Mehmet",
                    "due_day_of_week": "friday",
                    "due_explicit_date": None,
                    "source_quote": "ben hazırlarım",
                    "confidence": 0.9,
                }
            ]
        },
        system_contains="aksiyon maddesi",
    )

    result = await extract_action_items(provider, transcript_text=TRANSCRIPT, model="gpt-oss:20b")

    assert len(result.action_items) == 1
    assert result.action_items[0].owner == "Mehmet"
    assert result.action_items[0].due_day_of_week == "friday"


async def test_extract_decisions_returns_validated_schema():
    provider = FakeLLMProvider()
    provider.add_json_response(
        "Demo hazırlığını",
        {
            "decisions": [
                {
                    "summary": "Demo Cuma'ya kadar hazırlanacak",
                    "source_quote": "Cuma'ya kadar bitirelim mi",
                    "confidence": 0.8,
                }
            ]
        },
        system_contains="KARARLARI",
    )

    result = await extract_decisions(provider, transcript_text=TRANSCRIPT, model="gpt-oss:20b")

    assert len(result.decisions) == 1
    assert "Cuma" in result.decisions[0].summary


async def test_extract_action_items_and_decisions_do_not_cross_contaminate():
    """The same transcript text triggers both extractors; each must get
    its own scripted response based on the (different) system prompt."""
    provider = FakeLLMProvider()
    provider.add_json_response(
        "Demo hazırlığını", {"action_items": []}, system_contains="aksiyon maddesi"
    )
    provider.add_json_response("Demo hazırlığını", {"decisions": []}, system_contains="KARARLARI")

    actions = await extract_action_items(provider, transcript_text=TRANSCRIPT, model="gpt-oss:20b")
    decisions = await extract_decisions(provider, transcript_text=TRANSCRIPT, model="gpt-oss:20b")

    assert actions.action_items == []
    assert decisions.decisions == []


async def test_summarize_meeting_returns_prose_text():
    provider = FakeLLMProvider()
    provider.add_text_response("Demo hazırlığını", "Ayşe ve Mehmet demo hazırlığını konuştu.")

    summary = await summarize_meeting(provider, transcript_text=TRANSCRIPT, model="qwen3:14b")

    assert "demo hazırlığını" in summary.lower()
