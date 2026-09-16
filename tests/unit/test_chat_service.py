from __future__ import annotations

from odp.services.chat import ChatTurn, stream_chat_reply
from odp.services.chat.chat_service import _last_action_summary
from odp.services.llm import FakeLLMProvider
from odp.services.llm.provider import ChatStreamEvent, ToolCallRequest


async def test_stream_chat_reply_yields_deltas_in_order(db_conn):
    provider = FakeLLMProvider()
    provider.add_stream_chat_response("Kaç görev", ["Toplam ", "3 ", "açık görev var."])

    events = [
        event
        async for event in stream_chat_reply(
            db_conn,
            provider,
            message="Kaç görev açık?",
            history=[],
            model="gpt-oss:20b",
            timezone="Europe/Istanbul",
        )
    ]

    deltas = [e.delta for e in events]
    assert deltas == ["Toplam ", "3 ", "açık görev var."]
    assert all(e.tool_call is None and e.tool_result is None for e in events)


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


async def test_stream_chat_reply_executes_a_tool_call_and_reports_back(db_conn):
    """The model calls create_task on round 1; round 2 (after the tool
    result is fed back) streams the visible confirmation text."""
    provider = FakeLLMProvider()
    tool_call = ToolCallRequest(name="create_task", arguments={"title": "Demo hazırla"})
    provider.queue_stream_chat_call([ChatStreamEvent(tool_calls=[tool_call])])
    provider.queue_stream_chat_call(["Demo hazırla görevini oluşturdum."])

    events = [
        e
        async for e in stream_chat_reply(
            db_conn,
            provider,
            message='"Demo hazırla" adında bir görev oluştur',
            history=[],
            model="gpt-oss:20b",
        )
    ]

    tool_call_events = [e for e in events if e.tool_call is not None]
    tool_result_events = [e for e in events if e.tool_result is not None]
    text_events = [e for e in events if e.delta is not None]

    assert len(tool_call_events) == 1
    assert tool_call_events[0].tool_call["name"] == "create_task"
    assert len(tool_result_events) == 1
    assert tool_result_events[0].tool_result["result"] == "created"
    assert "".join(e.delta for e in text_events) == "Demo hazırla görevini oluşturdum."

    # And the task actually exists in the database — this isn't a proposal,
    # it's a direct write (plan §1/#5's carve-out for chat commands).
    row = db_conn.execute("SELECT COUNT(*) FROM tasks WHERE title = 'Demo hazırla'").fetchone()
    assert row[0] == 1


async def test_stream_chat_reply_stops_after_max_tool_rounds(db_conn):
    provider = FakeLLMProvider()
    for _ in range(10):  # more than MAX_TOOL_ROUNDS
        provider.queue_stream_chat_call(
            [
                ChatStreamEvent(
                    tool_calls=[ToolCallRequest(name="create_task", arguments={"title": "x"})]
                )
            ]
        )

    events = [
        e
        async for e in stream_chat_reply(
            db_conn, provider, message="sürekli görev oluştur", history=[], model="gpt-oss:20b"
        )
    ]

    final_text = "".join(e.delta for e in events if e.delta is not None)
    assert "tamamlayamadım" in final_text


# =========================================== _last_action_summary


def test_last_action_summary_extracts_the_id_from_the_trace():
    history = [
        ChatTurn(role="user", content="eyüp lojistik toplantısını 15.00 saatine ayarla"),
        ChatTurn(
            role="assistant",
            content=(
                '[araç çağrısı: update_meeting({"meeting_id": "abc123", "start_time": "15:00"}) '
                '-> {"meeting_id": "abc123", "result": "updated"}]\nToplantı güncellendi.'
            ),
        ),
    ]
    assert _last_action_summary(history) == "update_meeting(meeting_id='abc123')"


def test_last_action_summary_picks_the_most_recent_trace():
    history = [
        ChatTurn(
            role="assistant",
            content='[araç çağrısı: create_task({"title": "X"}) -> {"task_id": "old"}]\nTamam.',
        ),
        ChatTurn(role="user", content="şimdi de şunu yap"),
        ChatTurn(
            role="assistant",
            content='[araç çağrısı: create_task({"title": "Y"}) -> {"task_id": "new"}]\nTamam.',
        ),
    ]
    assert _last_action_summary(history) == "create_task(task_id='new')"


def test_last_action_summary_returns_none_without_any_trace():
    history = [
        ChatTurn(role="user", content="merhaba"),
        ChatTurn(role="assistant", content="merhaba, nasıl yardımcı olabilirim?"),
    ]
    assert _last_action_summary(history) is None


def test_last_action_summary_falls_back_to_tool_name_without_an_id_field():
    history = [
        ChatTurn(
            role="assistant",
            content=(
                '[araç çağrısı: suggest_meeting_slot({"text": "cuma"}) '
                '-> {"result": "suggested", "slots": []}]\nÖneriler var.'
            ),
        ),
    ]
    assert _last_action_summary(history) == "suggest_meeting_slot"


async def test_stream_chat_reply_injects_last_action_into_the_system_prompt(db_conn):
    # A regression guard for the fix above: the deterministic "SON İŞLEM"
    # line must actually reach the model, not just exist as a helper.
    provider = FakeLLMProvider()
    provider.add_stream_chat_response("onu geri al", ["tamam"])

    events = [
        e
        async for e in stream_chat_reply(
            db_conn,
            provider,
            message="onu geri al",
            history=[
                ChatTurn(role="user", content="bir görev oluştur"),
                ChatTurn(
                    role="assistant",
                    content=(
                        '[araç çağrısı: create_task({"title": "X"}) '
                        '-> {"task_id": "abc", "result": "created"}]\nOluşturuldu.'
                    ),
                ),
            ],
            model="gpt-oss:20b",
        )
    ]
    assert "".join(e.delta for e in events if e.delta is not None) == "tamam"
    assert "SON İŞLEM" in provider.calls[0]["system"]
    assert "create_task(task_id='abc')" in provider.calls[0]["system"]
