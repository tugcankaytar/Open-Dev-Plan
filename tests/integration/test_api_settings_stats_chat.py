from __future__ import annotations

import json

from httpx import ASGITransport, AsyncClient

from odp.api.app import create_app


async def test_get_dashboard_stats_returns_shape(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        response = await client.get("/api/stats/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "active_projects",
            "open_tasks",
            "overdue_tasks",
            "meetings",
            "pending_proposals",
            "task_status_counts",
            "weekly_activity",
        }
        assert len(body["weekly_activity"]) == 7


async def test_model_setting_get_returns_fallback_when_unreachable(tmp_settings, monkeypatch):
    # Force the "can't reach Ollama" path deterministically — asserting on
    # real environment state would pass or fail depending on whether a
    # local `ollama serve` happens to be running, which it may well be on
    # a dev machine (unlike CI, which is exactly why `gpu`-marked tests
    # are excluded there; this test isn't one of those, so it must not
    # depend on that either).
    async def _no_ollama(_host: str) -> list[str]:
        return []

    monkeypatch.setattr("odp.api.routers.settings._list_ollama_models", _no_ollama)

    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        response = await client.get("/api/settings/model")
        assert response.status_code == 200
        body = response.json()
        assert body["active_model"] == tmp_settings.extraction_model
        assert body["available_models"] == []


async def test_model_setting_put_skips_membership_check_when_ollama_unreachable(
    tmp_settings, monkeypatch
):
    async def _no_ollama(_host: str) -> list[str]:
        return []

    monkeypatch.setattr("odp.api.routers.settings._list_ollama_models", _no_ollama)

    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        # With no reachable Ollama, `available` comes back empty, so the
        # endpoint can't validate membership and must accept the write
        # rather than block the user from ever setting a model in dev/CI.
        put = await client.put("/api/settings/model", json={"model": "qwen3:14b"})
        assert put.status_code == 200
        assert put.json()["active_model"] == "qwen3:14b"

        get = await client.get("/api/settings/model")
        assert get.json()["active_model"] == "qwen3:14b"


async def test_model_setting_put_rejects_model_not_in_ollama(tmp_settings, monkeypatch):
    async def _some_models(_host: str) -> list[str]:
        return ["gpt-oss:20b", "qwen3:14b"]

    monkeypatch.setattr("odp.api.routers.settings._list_ollama_models", _some_models)

    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        response = await client.put("/api/settings/model", json={"model": "not-pulled:latest"})
        assert response.status_code == 422


async def test_chat_endpoint_streams_sse_deltas(tmp_settings, monkeypatch):
    from odp.services.llm import FakeLLMProvider

    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(transport=transport, base_url="http://test", timeout=10.0) as client,
        app.router.lifespan_context(app),
    ):
        fake = FakeLLMProvider()
        fake.add_stream_chat_response("Merhaba", ["Merhaba", "!"])
        app.state.llm_provider = fake

        response = await client.post("/api/chat", json={"message": "Merhaba", "history": []})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        deltas = [e["delta"] for e in events if "delta" in e]
        assert deltas == ["Merhaba", "!"]
        assert events[-1] == {"done": True}
