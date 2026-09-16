from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from odp.api.app import create_app


async def test_health_endpoint_reports_db_and_ollama_status(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"]["ok"] is True
    assert "ollama" in body
