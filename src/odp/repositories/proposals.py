"""CRUD for `proposals` — the human-approval gate on all AI output (plan §1/#5)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from odp.models import Proposal, ProposalKind, ProposalStatus, new_id
from odp.models.time import utc_now_iso


class ProposalsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        kind: ProposalKind,
        payload: dict[str, Any],
        source_meeting_id: str | None,
        source_segment_ids: list[str],
        confidence: float | None,
        prompt_version: str,
        model: str,
    ) -> Proposal:
        proposal = Proposal(
            id=new_id(),
            kind=kind,
            payload=payload,
            source_meeting_id=source_meeting_id,
            source_segment_ids=source_segment_ids,
            confidence=confidence,
            prompt_version=prompt_version,
            model=model,
            created_at=utc_now_iso(),
        )
        self._conn.execute(
            """
            INSERT INTO proposals
                (id, kind, payload_json, source_meeting_id, source_segment_ids_json,
                 confidence, prompt_version, model, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal.id,
                proposal.kind.value,
                json.dumps(proposal.payload),
                proposal.source_meeting_id,
                json.dumps(proposal.source_segment_ids),
                proposal.confidence,
                proposal.prompt_version,
                proposal.model,
                proposal.status.value,
                proposal.created_at,
            ),
        )
        return proposal

    def get(self, proposal_id: str) -> Proposal | None:
        row = self._conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        return self._row_to_proposal(row) if row else None

    def list_pending_for_meeting(self, meeting_id: str) -> list[Proposal]:
        rows = self._conn.execute(
            "SELECT * FROM proposals WHERE source_meeting_id = ? AND status = 'pending' "
            "ORDER BY created_at ASC",
            (meeting_id,),
        ).fetchall()
        return [self._row_to_proposal(row) for row in rows]

    def resolve(
        self,
        proposal_id: str,
        *,
        status: ProposalStatus,
        resolved_payload: dict[str, Any] | None = None,
        resolved_task_id: str | None = None,
    ) -> Proposal | None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE proposals SET status = ?, resolved_payload_json = ?, resolved_task_id = ?, "
            "resolved_at = ? WHERE id = ?",
            (
                status.value,
                json.dumps(resolved_payload) if resolved_payload is not None else None,
                resolved_task_id,
                now,
                proposal_id,
            ),
        )
        return self.get(proposal_id)

    @staticmethod
    def _row_to_proposal(row: sqlite3.Row) -> Proposal:
        return Proposal(
            id=row["id"],
            kind=ProposalKind(row["kind"]),
            payload=json.loads(row["payload_json"]),
            source_meeting_id=row["source_meeting_id"],
            source_segment_ids=json.loads(row["source_segment_ids_json"]),
            confidence=row["confidence"],
            prompt_version=row["prompt_version"],
            model=row["model"],
            status=ProposalStatus(row["status"]),
            resolved_payload=json.loads(row["resolved_payload_json"])
            if row["resolved_payload_json"]
            else None,
            resolved_task_id=row["resolved_task_id"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
        )
