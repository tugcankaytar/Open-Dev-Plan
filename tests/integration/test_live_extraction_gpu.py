"""Real end-to-end smoke test against actual local models — the plan §10
"Doğrulama" flow, automated: import a Turkish transcript, extract via
gpt-oss:20b, approve a proposal, confirm a Task exists. Requires a
running `ollama serve` with gpt-oss:20b + qwen3:14b pulled, so it's
excluded from the default CI run (-m "not gpu and not eval") and meant
to be run locally: `uv run pytest -m gpu`.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from odp.api.app import create_app
from odp.models import TranscriptSegment
from odp.repositories.meetings import MeetingsRepository

pytestmark = pytest.mark.gpu

TRANSCRIPT_TR = [
    "Ayşe: Herkese merhaba, bugün Eylül ayı demo hazırlığını konuşacağız.",
    "Mehmet: Ben demo sunumunu Cuma gününe kadar hazırlayabilirim.",
    "Ayşe: Harika, o zaman demo sunumunu senin hazırlaman konusunda anlaştık.",
    "Zeynep: Bütçe konusunda karar almamız lazım, 50 bin liralık ek bütçeyi onaylıyor muyuz?",
    "Ayşe: Evet, 50 bin liralık ek bütçeyi onaylıyoruz.",
    "Mehmet: Tamamdır, ben de haftaya kadar tasarım dosyalarını Zeynep'e gönderirim.",
]


async def test_live_meeting_extraction_end_to_end(tmp_settings):
    app = create_app(tmp_settings)
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(transport=transport, base_url="http://test", timeout=180.0) as client,
        app.router.lifespan_context(app),
    ):
        health = (await client.get("/api/health")).json()
        assert health["ollama"]["reachable"] is True, "ollama serve must be running for this test"

        meeting = (
            await client.post(
                "/api/meetings",
                json={
                    "title": "Demo Planlama Toplantısı",
                    "start_utc": "2026-09-16T09:00:00Z",
                    "end_utc": "2026-09-16T09:30:00Z",
                    "timezone": "Europe/Istanbul",
                },
            )
        ).json()

        # Insert a transcript directly (bypassing the not-yet-built Whisper
        # pipeline) so this test isolates the extraction stack.
        conn = app.state.db
        repo = MeetingsRepository(conn)
        segments = [
            TranscriptSegment(
                meeting_id=meeting["id"],
                seq=i,
                start_ms=i * 4000,
                end_ms=(i + 1) * 4000,
                text=t,
            )
            for i, t in enumerate(TRANSCRIPT_TR)
        ]
        repo.add_segments(segments)

        enqueued = (await client.post(f"/api/meetings/{meeting['id']}/extract")).json()
        job_id = enqueued["id"]

        job = None
        for _ in range(180):  # up to ~90s
            job = (await client.get(f"/api/jobs/{job_id}")).json()
            if job["status"] in ("succeeded", "failed"):
                break
            await asyncio.sleep(0.5)

        assert job is not None
        assert job["status"] == "succeeded", job.get("error")

        proposals = (await client.get(f"/api/meetings/{meeting['id']}/proposals")).json()
        assert len(proposals) >= 1, "expected at least one proposal (task/decision/summary)"

        task_proposals = [p for p in proposals if p["kind"] == "task"]
        kinds = [p["kind"] for p in proposals]
        assert task_proposals, f"expected at least one task proposal, got kinds: {kinds}"

        first_task_proposal = task_proposals[0]
        resolved = await client.post(
            f"/api/proposals/{first_task_proposal['id']}/resolve", json={"action": "approve"}
        )
        assert resolved.status_code == 200
        resolved_body = resolved.json()
        assert resolved_body["status"] == "approved"
        assert resolved_body["resolved_task_id"] is not None

        task = (await client.get(f"/api/tasks/{resolved_body['resolved_task_id']}")).json()
        assert task["title"]
        print(f"\n[live-gpu-test] extracted task: {task['title']!r} (owner={task['owner']!r})")
