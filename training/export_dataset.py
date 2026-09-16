#!/usr/bin/env python3
"""Export the `training_examples` table into an SFT-ready JSONL dataset
(plan §7).

    uv run python training/export_dataset.py --out training/dataset.jsonl

Every row in `training_examples` was written by resolve_proposal()
(src/odp/services/proposals/resolve.py) the moment a real user approved,
edited, or rejected an AI proposal — so this script only ever exports
data your own usage produced, never synthetic examples.

- approved / edited rows -> one SFT example each (edited rows use the
  user's correction as the target, not the model's original output —
  that correction IS the training signal).
- rejected rows are written to a separate file as DPO "rejected"
  completions. There's no paired "chosen" completion (the user didn't
  provide a correction, just a no), so building full DPO pairs needs
  either a later edit on a similar case or a human-written chosen
  completion — left as a manual/future step; see training/README.md.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

MIN_RECOMMENDED_EXAMPLES = 300  # plan §7: below this, improve the prompt instead


@dataclass(frozen=True, slots=True)
class SftExample:
    prompt: str
    completion: dict  # the target structured output (parsed JSON)


def _load_rows(conn: sqlite3.Connection, kind: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM training_examples WHERE kind = ? ORDER BY created_at ASC", (kind,)
    ).fetchall()


def build_sft_examples(conn: sqlite3.Connection) -> list[SftExample]:
    examples: list[SftExample] = []
    for row in _load_rows(conn, "sft"):
        target = row["user_correction_json"] or row["model_output_json"]
        examples.append(SftExample(prompt=row["transcript_excerpt"], completion=json.loads(target)))
    return examples


def build_dpo_rejected(conn: sqlite3.Connection) -> list[dict]:
    rows = _load_rows(conn, "dpo_pair")
    return [
        {
            "prompt": row["transcript_excerpt"],
            "rejected": json.loads(row["model_output_json"]),
        }
        for row in rows
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=None, help="Path to odp.db (default: from config)"
    )
    parser.add_argument("--out", type=Path, default=Path("training/dataset.jsonl"))
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.db is None:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from odp.config import get_settings

        db_path = get_settings().db_path
    else:
        db_path = args.db

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sft_examples = build_sft_examples(conn)
    rejected = build_dpo_rejected(conn)
    conn.close()

    print(f"Loaded {len(sft_examples)} SFT examples, {len(rejected)} DPO-rejected examples.")
    if len(sft_examples) < MIN_RECOMMENDED_EXAMPLES:
        print(
            f"NOTE: below the recommended minimum of {MIN_RECOMMENDED_EXAMPLES} examples — "
            "per plan §7, improving the prompt (services/prompts/v1/) will likely help more "
            "than fine-tuning at this dataset size. Keep using the app to accumulate more "
            "approved/edited proposals."
        )

    random.seed(args.seed)
    shuffled = list(sft_examples)
    random.shuffle(shuffled)
    val_count = max(1, int(len(shuffled) * args.val_fraction)) if shuffled else 0
    val_set, train_set = shuffled[:val_count], shuffled[val_count:]

    def to_row(ex: SftExample) -> dict:
        return {
            "messages": [
                {"role": "user", "content": ex.prompt},
                {"role": "assistant", "content": json.dumps(ex.completion, ensure_ascii=False)},
            ]
        }

    train_path = args.out
    val_path = args.out.with_name(args.out.stem + ".val" + args.out.suffix)
    rejected_path = args.out.with_name(args.out.stem + ".rejected" + args.out.suffix)

    write_jsonl(train_path, [to_row(e) for e in train_set])
    write_jsonl(val_path, [to_row(e) for e in val_set])
    write_jsonl(rejected_path, rejected)

    print(f"Wrote {len(train_set)} train examples -> {train_path}")
    print(f"Wrote {len(val_set)} val examples -> {val_path}")
    print(f"Wrote {len(rejected)} rejected examples -> {rejected_path}")


if __name__ == "__main__":
    main()
