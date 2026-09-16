"""Insert-only log for the fine-tuning dataset source (plan §7).

A row is written every time a proposal is resolved: approved-as-is and
edited proposals become SFT examples (the edit is the human correction);
rejected proposals become the "rejected" half of a DPO-style pair. This
table is the join point `training/export_dataset.py` will read from.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from odp.models import new_id
from odp.models.time import utc_now_iso


class TrainingExamplesRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record(
        self,
        *,
        proposal_id: str,
        kind: str,
        transcript_excerpt: str,
        model_output: dict[str, Any],
        user_correction: dict[str, Any] | None,
    ) -> str:
        example_id = new_id()
        self._conn.execute(
            """
            INSERT INTO training_examples
                (id, proposal_id, kind, transcript_excerpt, model_output_json,
                 user_correction_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                example_id,
                proposal_id,
                kind,
                transcript_excerpt,
                json.dumps(model_output),
                json.dumps(user_correction) if user_correction is not None else None,
                utc_now_iso(),
            ),
        )
        return example_id
