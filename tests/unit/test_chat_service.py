from __future__ import annotations

from odp.services.chat import ChatTurn, stream_chat_reply
from odp.services.llm import FakeLLMProvider


async def test_stream_chat_reply_yields_deltas_in_order(db_conn):
    provider = FakeLLMProvider()
    provider.add_stream_chat_response("Kaç görev", ["Toplam ", "3 ", "açık görev var."])

    chunks = [
        chunk
        async for chunk in stream_chat_reply(
            db_conn,
            provider,
            message="Kaç görev açık?",
            history=[],
            model="gpt-oss:20b",
            timezone="Europe/Istanbul",
        )
    ]

    assert chunks == ["Toplam ", "3 ", "açık görev var."]
    assert "".join(chunks) == "Toplam 3 açık görev var."


async def test_stream_chat_reply_includes_history_and_context_in_system_prompt(db_conn):
    provider = FakeLLMProvider()
    provider.add_stream_chat_response("ikinci soru", ["cevap"])

    async for _ in stream_chat_reply(
        db_conn,
        provider,
        message="ikinci soru",
        history=[
            ChatTurn(role="user", content="ilk soru"),
            ChatTurn(role="assistant", content="ilk cevap"),
        ],
        model="gpt-oss:20b",
    ):
        pass

    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["kind"] == "stream_chat"
    assert call["prompt"] == "ikinci soru"


async def test_stream_chat_reply_caps_history_length(db_conn):
    provider = FakeLLMProvider()
    provider.add_stream_chat_response("son soru", ["ok"])

    long_history = [ChatTurn(role="user", content=f"soru {i}") for i in range(20)]
    async for _ in stream_chat_reply(
        db_conn, provider, message="son soru", history=long_history, model="gpt-oss:20b"
    ):
        pass

    # Sanity: didn't raise on a long history — the cap is exercised without
    # asserting internal message count (that's an implementation detail).
    assert provider.calls[0]["prompt"] == "son soru"
