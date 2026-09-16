from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from odp.api.app import create_app


async def test_import_transcript_text_endpoint(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        meeting = (
            await client.post(
                "/api/meetings",
                json={
                    "title": "Test",
                    "start_utc": "2026-09-16T09:00:00Z",
                    "end_utc": "2026-09-16T09:30:00Z",
                    "timezone": "Europe/Istanbul",
                },
            )
        ).json()

        imported = await client.post(
            f"/api/meetings/{meeting['id']}/transcript/import-text",
            json={"text": "Ayşe: Merhaba\nMehmet: Selam"},
        )
        assert imported.status_code == 200
        assert len(imported.json()) == 2

        fetched = await client.get(f"/api/meetings/{meeting['id']}/transcript")
        assert len(fetched.json()) == 2


async def test_import_transcript_text_404_for_unknown_meeting(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        response = await client.post(
            "/api/meetings/does-not-exist/transcript/import-text", json={"text": "x"}
        )
        assert response.status_code == 404
