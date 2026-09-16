"""HTTP-level CRUD coverage for the API layer. No LLM calls are triggered
here — the background worker's real OllamaProvider just idles since
nothing gets enqueued (see the gpu-marked live test for an end-to-end
run against real models)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from odp.api.app import create_app
from odp.models import Meeting
from odp.services.calendar import export_meetings_to_ics


async def test_project_crud_round_trip(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        created = await client.post("/api/projects", json={"name": "Website Yenileme"})
        assert created.status_code == 201
        project = created.json()
        assert project["name"] == "Website Yenileme"
        assert project["status"] == "active"

        listed = await client.get("/api/projects")
        assert listed.status_code == 200
        assert any(p["id"] == project["id"] for p in listed.json())

        updated = await client.patch(f"/api/projects/{project['id']}", json={"status": "paused"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "paused"

        deleted = await client.delete(f"/api/projects/{project['id']}")
        assert deleted.status_code == 204

        missing = await client.get(f"/api/projects/{project['id']}")
        assert missing.status_code == 404


async def test_task_crud_and_dependencies(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        t1 = (await client.post("/api/tasks", json={"title": "Tasarım"})).json()
        t2 = (await client.post("/api/tasks", json={"title": "Geliştirme"})).json()

        dep = await client.post(
            f"/api/tasks/{t2['id']}/dependencies", json={"depends_on_task_id": t1["id"]}
        )
        assert dep.status_code == 201

        patched = await client.patch(f"/api/tasks/{t1['id']}", json={"status": "done"})
        assert patched.status_code == 200
        assert patched.json()["status"] == "done"

        listed = await client.get("/api/tasks")
        assert len(listed.json()) == 2


async def test_meeting_crud_and_ics_export(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        created = await client.post(
            "/api/meetings",
            json={
                "title": "Haftalık Sync",
                "start_utc": "2026-09-22T07:00:00Z",
                "end_utc": "2026-09-22T07:30:00Z",
                "timezone": "Europe/Istanbul",
            },
        )
        assert created.status_code == 201
        meeting = created.json()

        transcript = await client.get(f"/api/meetings/{meeting['id']}/transcript")
        assert transcript.status_code == 200
        assert transcript.json() == []

        export = await client.get("/api/calendar/export.ics")
        assert export.status_code == 200
        assert export.headers["content-type"].startswith("text/calendar")
        assert "Haftalık Sync".encode() in export.content


async def test_calendar_import_preview_does_not_persist(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    ics = export_meetings_to_ics(
        [
            Meeting(
                title="Dışarıdan İçe Aktarılan",
                start_utc="2026-09-22T07:00:00Z",
                end_utc="2026-09-22T07:30:00Z",
                timezone="Europe/Istanbul",
                created_at="2026-09-16T00:00:00Z",
                updated_at="2026-09-16T00:00:00Z",
            )
        ]
    )
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        preview = await client.post(
            "/api/calendar/import", json={"ics_text": ics.decode("utf-8"), "persist": False}
        )
        assert preview.status_code == 200
        assert len(preview.json()) == 1

        listed = await client.get("/api/meetings")
        assert listed.json() == []  # preview must not have persisted anything

        persisted = await client.post(
            "/api/calendar/import", json={"ics_text": ics.decode("utf-8"), "persist": True}
        )
        assert persisted.status_code == 200

        listed_again = await client.get("/api/meetings")
        assert len(listed_again.json()) == 1


async def test_proposal_resolve_returns_409_for_unknown_id(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        response = await client.post(
            "/api/proposals/does-not-exist/resolve", json={"action": "approve"}
        )
        assert response.status_code == 409


async def test_job_enqueue_and_lookup(tmp_settings):
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
                    "title": "X",
                    "start_utc": "2026-09-22T07:00:00Z",
                    "end_utc": "2026-09-22T07:30:00Z",
                    "timezone": "Europe/Istanbul",
                },
            )
        ).json()

        enqueued = await client.post(f"/api/meetings/{meeting['id']}/extract")
        assert enqueued.status_code == 202
        job = enqueued.json()
        assert job["job_type"] == "extraction"
        assert job["status"] == "queued"

        fetched = await client.get(f"/api/jobs/{job['id']}")
        assert fetched.status_code == 200
