"""End-to-end extraction pipeline test (FakeLLMProvider, real SQLite).

Asserts the invariant from plan §1/#5: extraction NEVER writes to the
`tasks` table directly — everything lands as a `proposals` row with
provenance back to the transcript segment it came from.
"""

from __future__ import annotations

from odp.models import Meeting, ProposalKind, ProposalStatus, TranscriptSegment
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.services.extraction.pipeline import extract_meeting
from odp.services.llm import FakeLLMProvider

SEG1_TEXT = "Ayşe: Demo hazırlığını Cuma'ya kadar bitirelim mi?"
SEG2_TEXT = "Mehmet: Tamam, ben hazırlarım."


async def test_extract_meeting_creates_proposals_never_tasks(db_conn):
    meetings_repo = MeetingsRepository(db_conn)
    proposals_repo = ProposalsRepository(db_conn)

    meeting = meetings_repo.create(
        Meeting(
            title="Demo planlama",
            start_utc="2026-09-16T09:00:00Z",
            end_utc="2026-09-16T09:30:00Z",
            timezone="Europe/Istanbul",
            created_at="x",
            updated_at="x",
        )
    )
    seg1 = TranscriptSegment(meeting_id=meeting.id, seq=0, start_ms=0, end_ms=3000, text=SEG1_TEXT)
    seg2 = TranscriptSegment(
        meeting_id=meeting.id, seq=1, start_ms=3000, end_ms=5000, text=SEG2_TEXT
    )
    meetings_repo.add_segments([seg1, seg2])

    provider = FakeLLMProvider()
    provider.add_json_response(
        "Cuma'ya kadar bitirelim",
        {
            "action_items": [
                {
                    "title": "Demo hazırlığını bitir",
                    "owner": "Mehmet",
                    "due_day_of_week": "friday",
                    "due_explicit_date": None,
                    "source_quote": SEG2_TEXT,
                    "confidence": 0.9,
                }
            ]
        },
        system_contains="aksiyon maddesi çıkaran",
    )
    provider.add_json_response(
        "Cuma'ya kadar bitirelim",
        {
            "decisions": [
                {
                    "summary": "Demo Cuma'ya kadar hazır olacak",
                    "source_quote": SEG1_TEXT,
                    "confidence": 0.8,
                }
            ]
        },
        system_contains="alınan KARARLARI",
    )
    provider.add_text_response(
        "Cuma'ya kadar bitirelim",
        "Ayşe ve Mehmet demo hazırlığını Cuma'ya kadar tamamlamayı konuştu.",
    )

    result = await extract_meeting(
        db_conn,
        provider,
        meeting_id=meeting.id,
        extraction_model="gpt-oss:20b",
        prose_model="qwen3:14b",
        embedding_model="bge-m3",
    )

    assert len(result.task_proposal_ids) == 1
    assert len(result.decision_proposal_ids) == 1
    assert result.summary_proposal_id

    # Nothing was written to `tasks` — every AI output is a pending proposal.
    task_count = db_conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    assert task_count == 0

    task_proposal = proposals_repo.get(result.task_proposal_ids[0])
    assert task_proposal is not None
    assert task_proposal.kind == ProposalKind.task
    assert task_proposal.status == ProposalStatus.pending
    assert task_proposal.payload["title"] == "Demo hazırlığını bitir"
    assert seg2.id in task_proposal.source_segment_ids  # provenance traces to the right segment

    decision_proposal = proposals_repo.get(result.decision_proposal_ids[0])
    assert decision_proposal is not None
    assert decision_proposal.kind == ProposalKind.decision
    assert seg1.id in decision_proposal.source_segment_ids

    summary_proposal = proposals_repo.get(result.summary_proposal_id)
    assert summary_proposal is not None
    assert summary_proposal.kind == ProposalKind.summary
    assert "demo" in summary_proposal.payload["summary"].lower()

    updated_meeting = meetings_repo.get(meeting.id)
    assert updated_meeting is not None
    assert updated_meeting.status.value == "processed"
