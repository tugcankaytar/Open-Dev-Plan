#!/usr/bin/env python3
"""Compare extraction-model candidates on the golden set (plan §8/§2).

    uv run python evals/run_eval.py --model gpt-oss:20b --model qwen3:14b

This is the tool that turns "which model should extraction use?" from an
assumption into a measurement — run it whenever you're considering a
model swap, and whenever `services/prompts/v1/*.md` changes materially.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from metrics import CaseResult, ModelSummary, score_case, summarize

from odp.services.extraction.actions import extract_action_items
from odp.services.extraction.decisions import extract_decisions
from odp.services.llm.ollama_provider import OllamaProvider
from odp.services.llm.structured import StructuredGenerationError

GOLDEN_DIR = Path(__file__).parent / "golden"
DEFAULT_MODELS = ["gpt-oss:20b", "qwen3:14b"]


def load_cases() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(GOLDEN_DIR.glob("*.json"))]


async def run_case(provider: OllamaProvider, case: dict, model: str) -> CaseResult:
    transcript_text = "\n".join(case["transcript"])
    started = time.monotonic()
    try:
        actions, decisions = await asyncio.gather(
            extract_action_items(provider, transcript_text=transcript_text, model=model),
            extract_decisions(provider, transcript_text=transcript_text, model=model),
        )
    except StructuredGenerationError as exc:
        elapsed = time.monotonic() - started
        return CaseResult(
            case_id=case["id"],
            model=model,
            action_titles=[],
            decision_summaries=[],
            keyword_recall=0.0,
            turkish_rate=0.0,
            latency_s=elapsed,
            errors=[f"structured generation failed: {exc}"],
        )
    elapsed = time.monotonic() - started

    return score_case(
        case,
        model=model,
        action_titles=[a.title for a in actions.action_items],
        action_owners=[a.owner for a in actions.action_items],
        action_due_flags=[
            bool(a.due_day_of_week or a.due_explicit_date) for a in actions.action_items
        ],
        decision_summaries=[d.summary for d in decisions.decisions],
        latency_s=elapsed,
    )


def print_report(results: list[CaseResult], models: list[str]) -> None:
    print("\n=== Per-case results ===")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(
            f"[{status}] {r.model:>12} | {r.case_id:<28} | "
            f"{r.latency_s:5.1f}s | recall={r.keyword_recall:.2f}"
        )
        if r.action_titles:
            print(f"           action_titles: {r.action_titles}")
        if r.decision_summaries:
            print(f"           decisions:     {r.decision_summaries}")
        for err in r.errors:
            print(f"           ! {err}")

    print("\n=== Model summary ===")
    summaries: list[ModelSummary] = [summarize(results, m) for m in models]
    header = f"{'model':<16} {'pass':>8} {'recall':>8} {'turkish%':>9} {'avg_s':>7}"
    print(header)
    print("-" * len(header))
    for s in summaries:
        print(
            f"{s.model:<16} {s.cases_passed:>4}/{s.cases_total:<3} "
            f"{s.mean_keyword_recall:>8.2f} "
            f"{s.mean_turkish_rate * 100:>8.1f}% {s.mean_latency_s:>6.1f}s"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", dest="models", help="Model tag (repeatable)")
    parser.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--json-out", type=Path, default=None, help="Optional path to write raw results as JSON"
    )
    args = parser.parse_args()

    models = args.models or DEFAULT_MODELS
    provider = OllamaProvider(args.ollama_host, timeout_s=180.0)
    cases = load_cases()

    print(f"Running {len(cases)} golden cases against {len(models)} model(s): {models}")

    results: list[CaseResult] = []
    for model in models:
        for case in cases:
            result = await run_case(provider, case, model)
            results.append(result)

    print_report(results, models)

    if args.json_out:
        args.json_out.write_text(
            json.dumps([r.__dict__ for r in results], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nWrote raw results to {args.json_out}")


if __name__ == "__main__":
    asyncio.run(main())
