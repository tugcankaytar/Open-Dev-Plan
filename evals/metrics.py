"""Scoring for a single golden-case run against a single model.

Deliberately simple, deterministic checks (substring/keyword matching,
count ranges) rather than "ask another LLM to judge" — an eval harness
whose grader is itself an unreliable LLM call is not trustworthy for the
one thing it exists to answer (plan §8: which model to use, backed by
data, not vibes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TURKISH_CHARS = set("çğıöşüÇĞİÖŞÜ")


def contains_turkish_chars(text: str) -> bool:
    return any(ch in TURKISH_CHARS for ch in text)


@dataclass
class CaseResult:
    case_id: str
    model: str
    action_titles: list[str]
    decision_summaries: list[str]
    keyword_recall: float
    turkish_rate: float
    latency_s: float
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def score_case(
    case: dict[str, Any],
    *,
    model: str,
    action_titles: list[str],
    action_owners: list[str | None],
    action_due_flags: list[bool],
    decision_summaries: list[str],
    latency_s: float,
) -> CaseResult:
    errors: list[str] = []

    keyword_groups: list[list[str]] = case.get("expected_action_keywords", [])
    matched = sum(
        1
        for group in keyword_groups
        if any(all(kw.lower() in title.lower() for kw in group) for title in action_titles)
    )
    keyword_recall = matched / len(keyword_groups) if keyword_groups else 1.0
    if keyword_recall < 1.0:
        errors.append(f"keyword recall {keyword_recall:.2f} < 1.0 (titles: {action_titles})")

    lo, hi = case["expected_action_count_min"], case["expected_action_count_max"]
    if not (lo <= len(action_titles) <= hi):
        errors.append(f"action count {len(action_titles)} outside [{lo}, {hi}]")

    dlo, dhi = case["expected_decision_count_min"], case["expected_decision_count_max"]
    if not (dlo <= len(decision_summaries) <= dhi):
        errors.append(f"decision count {len(decision_summaries)} outside [{dlo}, {dhi}]")

    expected_owner = case.get("expected_owner_contains")
    if expected_owner:
        owner_ok = any(o and expected_owner.lower() in o.lower() for o in action_owners)
        if not owner_ok:
            errors.append(
                f"expected owner containing {expected_owner!r} not found in {action_owners}"
            )

    if case.get("forbid_due_date") and any(action_due_flags):
        errors.append("model fabricated a due date/day despite an ambiguous timeframe")

    turkish_rate = (
        sum(1 for t in action_titles if contains_turkish_chars(t)) / len(action_titles)
        if action_titles
        else 1.0
    )

    return CaseResult(
        case_id=case["id"],
        model=model,
        action_titles=action_titles,
        decision_summaries=decision_summaries,
        keyword_recall=keyword_recall,
        turkish_rate=turkish_rate,
        latency_s=latency_s,
        errors=errors,
    )


@dataclass
class ModelSummary:
    model: str
    cases_passed: int
    cases_total: int
    mean_keyword_recall: float
    mean_turkish_rate: float
    mean_latency_s: float


def summarize(results: list[CaseResult], model: str) -> ModelSummary:
    model_results = [r for r in results if r.model == model]
    n = len(model_results)
    return ModelSummary(
        model=model,
        cases_passed=sum(1 for r in model_results if r.passed),
        cases_total=n,
        mean_keyword_recall=sum(r.keyword_recall for r in model_results) / n if n else 0.0,
        mean_turkish_rate=sum(r.turkish_rate for r in model_results) / n if n else 0.0,
        mean_latency_s=sum(r.latency_s for r in model_results) / n if n else 0.0,
    )
