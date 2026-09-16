"""Covers the pure-function pieces of OllamaProvider that don't need a
real Ollama server — see the ``-m gpu`` tests for the live-model path."""

from __future__ import annotations

from odp.services.llm.ollama_provider import _clean_tool_name


def test_clean_tool_name_strips_harmony_channel_marker():
    # Observed live: gpt-oss occasionally leaks its harmony-format channel
    # tag into the parsed tool name instead of a clean function name.
    assert _clean_tool_name("suggest_meeting_slot<|channel|>commentary") == "suggest_meeting_slot"


def test_clean_tool_name_leaves_a_normal_name_untouched():
    assert _clean_tool_name("create_task") == "create_task"
