"""Orchestrates meeting extraction: transcript -> proposals.

Ties together chunking (§6), the three extractors, dedup, and provenance
matching. The one invariant every step here respects: nothing lands in
`tasks` or any other domain table — everything becomes a row in
`proposals`, for a human to approve, edit, or reject (plan §1/#5).
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass

from odp.models import MeetingStatus, Proposal, ProposalKind, TranscriptSegment
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.services.extraction.actions import ACTION_ITEMS_PROMPT, extract_action_items
from odp.services.extraction.chunking import chunk_segments, fits_in_single_call, render_transcript
from odp.services.extraction.decisions import DECISIONS_PROMPT, extract_decisions
from odp.services.extraction.dedupe import deduplicate_action_items, deduplicate_decisions
from odp.services.extraction.schemas import ExtractedActionItem, ExtractedDecision
from odp.services.extraction.summarize import SUMMARY_PROMPT, summarize_meeting
from odp.services.llm.provider import LLMProvider


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    task_proposal_ids: list[str]
    decision_proposal_ids: list[str]
    summary_proposal_id: str


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _find_source_segment_ids(quote: str, segments: list[TranscriptSegment]) -> list[str]:
    """Match a model-quoted excerpt back to the transcript segment(s) it
    came from, via normalized substring containment. A miss (model
    paraphrased despite instructions) just means an empty provenance
    list — never an error, since the proposal is still useful without it.
    """
    normalized_quote = _normalize(quote)
    if not normalized_quote:
        return []
    return [seg.id for seg in segments if normalized_quote in _normalize(seg.text)]


async def _process_chunk(
    provider: LLMProvider, chunk: list[TranscriptSegment], model: str
) -> tuple[list[ExtractedActionItem], list[ExtractedDecision]]:
    text = render_transcript(chunk)
    actions, decisions = await asyncio.gather(
        extract_action_items(provider, transcript_text=text, model=model),
        extract_decisions(provider, transcript_text=text, model=model),
    )
    return actions.action_items, decisions.decisions


async def _summarize_meeting_possibly_long(
    provider: LLMProvider, segments: list[TranscriptSegment], model: str, max_tokens: int
) -> str:
    if fits_in_single_call(segments, max_tokens):
        text = render_transcript(segments)
        return await summarize_meeting(provider, transcript_text=text, model=model)

    # Reduce step: summarize each chunk independently, then summarize the
    # summaries — never chain one chunk's output into the next chunk's
    # prompt (that's what made the draft plan's version error-compounding).
    chunks = chunk_segments(segments, max_tokens=max_tokens)
    partial_summaries = await asyncio.gather(
        *(
            summarize_meeting(provider, transcript_text=render_transcript(c), model=model)
            for c in chunks
        )
    )
    combined = "\n\n".join(f"Bölüm {i + 1}: {s}" for i, s in enumerate(partial_summaries))
    return await summarize_meeting(provider, transcript_text=combined, model=model)


async def extract_meeting(
    conn: sqlite3.Connection,
    provider: LLMProvider,
    *,
    meeting_id: str,
    extraction_model: str,
    prose_model: str,
    embedding_model: str,
    max_context_tokens: int = 16_000,
) -> ExtractionResult:
    meetings_repo = MeetingsRepository(conn)
    proposals_repo = ProposalsRepository(conn)

    segments = meetings_repo.get_segments(meeting_id)
    if not segments:
        raise ValueError(f"no transcript segments for meeting {meeting_id}")

    chunks = chunk_segments(segments, max_tokens=max_context_tokens)
    chunk_results = await asyncio.gather(
        *(_process_chunk(provider, chunk, extraction_model) for chunk in chunks)
    )

    raw_actions = [item for actions, _ in chunk_results for item in actions]
    raw_decisions = [item for _, decisions in chunk_results for item in decisions]

    deduped_actions = await deduplicate_action_items(
        provider, raw_actions, embedding_model=embedding_model
    )
    deduped_decisions = await deduplicate_decisions(
        provider, raw_decisions, embedding_model=embedding_model
    )

    task_proposal_ids: list[str] = []
    for item in deduped_actions:
        proposal = proposals_repo.create(
            kind=ProposalKind.task,
            payload=item.model_dump(mode="json"),
            source_meeting_id=meeting_id,
            source_segment_ids=_find_source_segment_ids(item.source_quote, segments),
            confidence=item.confidence,
            prompt_version=ACTION_ITEMS_PROMPT.prompt_version,
            model=extraction_model,
        )
        task_proposal_ids.append(proposal.id)

    decision_proposal_ids: list[str] = []
    for decision in deduped_decisions:
        proposal = proposals_repo.create(
            kind=ProposalKind.decision,
            payload=decision.model_dump(mode="json"),
            source_meeting_id=meeting_id,
            source_segment_ids=_find_source_segment_ids(decision.source_quote, segments),
            confidence=decision.confidence,
            prompt_version=DECISIONS_PROMPT.prompt_version,
            model=extraction_model,
        )
        decision_proposal_ids.append(proposal.id)

    summary_text = await _summarize_meeting_possibly_long(
        provider, segments, prose_model, max_context_tokens
    )
    summary_proposal: Proposal = proposals_repo.create(
        kind=ProposalKind.summary,
        payload={"summary": summary_text},
        source_meeting_id=meeting_id,
        source_segment_ids=[],
        confidence=None,
        prompt_version=SUMMARY_PROMPT.prompt_version,
        model=prose_model,
    )

    meetings_repo.update_status(meeting_id, MeetingStatus.processed)

    return ExtractionResult(
        task_proposal_ids=task_proposal_ids,
        decision_proposal_ids=decision_proposal_ids,
        summary_proposal_id=summary_proposal.id,
    )
