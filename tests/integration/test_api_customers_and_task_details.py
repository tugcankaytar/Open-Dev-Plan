from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from odp.api.app import create_app


async def test_customer_crud_and_project_link(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        customer = (await client.post("/api/customers", json={"name": "Acme A.Ş."})).json()
        assert customer["name"] == "Acme A.Ş."

        project = (
            await client.post(
                "/api/projects", json={"name": "Web Sitesi", "customer_id": customer["id"]}
            )
        ).json()
        assert project["customer_id"] == customer["id"]

        filtered = await client.get(f"/api/projects?customer_id={customer['id']}")
        assert len(filtered.json()) == 1

        # Explicit clear via PATCH must actually null the field, not skip it.
        cleared = await client.patch(f"/api/projects/{project['id']}", json={"customer_id": None})
        assert cleared.json()["customer_id"] is None

        deleted = await client.delete(f"/api/customers/{customer['id']}")
        assert deleted.status_code == 204
        assert (await client.get(f"/api/customers/{customer['id']}")).status_code == 404


async def test_task_create_with_detail_fields_and_checklist(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        task = (
            await client.post(
                "/api/tasks",
                json={
                    "title": "Tasarım",
                    "priority": "high",
                    "start_utc": "2026-09-20T09:00:00Z",
                    "tags": ["backend", "acil"],
                },
            )
        ).json()
        assert task["priority"] == "high"
        assert task["tags"] == ["backend", "acil"]
        assert task["checklist_total"] == 0

        item1 = (
            await client.post(f"/api/tasks/{task['id']}/checklist", json={"title": "Wireframe"})
        ).json()
        await client.post(f"/api/tasks/{task['id']}/checklist", json={"title": "Renk paleti"})

        refetched = (await client.get(f"/api/tasks/{task['id']}")).json()
        assert refetched["checklist_total"] == 2
        assert refetched["checklist_done"] == 0

        toggled = await client.patch(f"/api/tasks/checklist/{item1['id']}", json={"done": True})
        assert toggled.status_code == 204

        refetched_again = (await client.get(f"/api/tasks/{task['id']}")).json()
        assert refetched_again["checklist_done"] == 1

        checklist = (await client.get(f"/api/tasks/{task['id']}/checklist")).json()
        assert [i["title"] for i in checklist] == ["Wireframe", "Renk paleti"]

        removed = await client.delete(f"/api/tasks/checklist/{item1['id']}")
        assert removed.status_code == 204
        assert len((await client.get(f"/api/tasks/{task['id']}/checklist")).json()) == 1


async def test_task_update_changes_priority_and_tags(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        task = (await client.post("/api/tasks", json={"title": "X"})).json()
        assert task["priority"] == "medium"

        updated = await client.patch(
            f"/api/tasks/{task['id']}", json={"priority": "urgent", "tags": ["önemli"]}
        )
        body = updated.json()
        assert body["priority"] == "urgent"
        assert body["tags"] == ["önemli"]
