"""Covers training/export_dataset.py — loaded by file path since
`training/` is a standalone script directory, not part of the `odp`
package."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from odp.db import open_db

_SPEC = importlib.util.spec_from_file_location(
    "export_dataset", Path(__file__).parent.parent.parent / "training" / "export_dataset.py"
)
assert _SPEC is not None and _SPEC.loader is not None
export_dataset = importlib.util.module_from_spec(_SPEC)
sys.modules["export_dataset"] = export_dataset  # dataclass field resolution needs this registered
_SPEC.loader.exec_module(export_dataset)


def _seed_training_example(conn: sqlite3.Connection, *, kind: str, correction: dict | None) -> None:
    proposal_id = f"prop-{kind}-{correction}"
    conn.execute(
        """
        INSERT INTO proposals
            (id, kind, payload_json, source_segment_ids_json, prompt_version, model,
             status, created_at)
        VALUES (?, 'task', '{}', '[]', 'action_items/v1/deadbeef', 'gpt-oss:20b',
                'approved', '2026-09-16T00:00:00Z')
        """,
        (proposal_id,),
    )
    conn.execute(
        """
        INSERT INTO training_examples
            (id, proposal_id, kind, transcript_excerpt, model_output_json,
             user_correction_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, '2026-09-16T00:00:00Z')
        """,
        (
            f"ex-{kind}-{correction}",
            proposal_id,
            kind,
            "Mehmet: ben hazırlarım.",
            json.dumps({"title": "Yanlış başlık"}),
            json.dumps(correction) if correction is not None else None,
        ),
    )


def test_build_sft_examples_prefers_user_correction_over_model_output(tmp_settings):
    tmp_settings.ensure_dirs()
    conn = open_db(tmp_settings.db_path)
    _seed_training_example(conn, kind="sft", correction={"title": "Doğru başlık"})
    _seed_training_example(conn, kind="sft", correction=None)

    examples = export_dataset.build_sft_examples(conn)

    assert len(examples) == 2
    assert {e.completion["title"] for e in examples} == {"Doğru başlık", "Yanlış başlık"}
    conn.close()


def test_build_dpo_rejected_only_includes_rejected_kind(tmp_settings):
    tmp_settings.ensure_dirs()
    conn = open_db(tmp_settings.db_path)
    _seed_training_example(conn, kind="sft", correction=None)
    _seed_training_example(conn, kind="dpo_pair", correction=None)

    rejected = export_dataset.build_dpo_rejected(conn)

    assert len(rejected) == 1
    assert rejected[0]["rejected"]["title"] == "Yanlış başlık"
    conn.close()


def test_write_jsonl_round_trips(tmp_path):
    out_path = tmp_path / "out.jsonl"
    rows = [{"a": 1}, {"b": "Türkçe metin"}]

    export_dataset.write_jsonl(out_path, rows)

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == rows
