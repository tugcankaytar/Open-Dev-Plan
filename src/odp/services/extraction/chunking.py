"""Map-reduce chunking for long transcripts (plan §6).

The draft plan's original approach was a sequential chain where each
chunk's summary fed into the next as "context" — slow, and errors
compound (by chunk 10, chunk 1's meaning has drifted). Here: measure
first, and only split if the transcript actually exceeds the model's
usable context; when it does, chunks are processed independently
(map, done by the caller via asyncio.gather) with a small overlap so an
action item mentioned right at a chunk boundary isn't missed, then
merged (reduce) via dedupe.py — never chained.
"""

from __future__ import annotations

from odp.models import TranscriptSegment

# Conservative chars-per-token estimate. We deliberately overestimate
# token count (i.e. use a low chars/token ratio) rather than risk
# overflowing the model's context window — Turkish's agglutinative
# morphology tends to produce more subword tokens per character than
# English. This is a heuristic, not a real tokenizer count.
CHARS_PER_TOKEN_ESTIMATE = 3.2


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / CHARS_PER_TOKEN_ESTIMATE))


def render_transcript(segments: list[TranscriptSegment]) -> str:
    """Render segments as speaker-labeled lines for an LLM prompt."""
    lines = []
    for s in segments:
        prefix = f"[{s.speaker}] " if s.speaker else ""
        lines.append(f"{prefix}{s.text}")
    return "\n".join(lines)


def fits_in_single_call(segments: list[TranscriptSegment], max_tokens: int) -> bool:
    return estimate_tokens(render_transcript(segments)) <= max_tokens


def chunk_segments(
    segments: list[TranscriptSegment],
    *,
    max_tokens: int,
    overlap_fraction: float = 0.1,
) -> list[list[TranscriptSegment]]:
    """Split segments into token-bounded, overlapping groups.

    Returns a single chunk containing everything if it already fits —
    chunking is the exception, not the default path (plan §6 step 1).
    """
    if not segments:
        return []
    if fits_in_single_call(segments, max_tokens):
        return [segments]

    chunks: list[list[TranscriptSegment]] = []
    start = 0
    n = len(segments)
    while start < n:
        end = start
        token_budget = 0
        while end < n:
            seg_tokens = estimate_tokens(segments[end].text)
            if token_budget + seg_tokens > max_tokens and end > start:
                break
            token_budget += seg_tokens
            end += 1
        chunks.append(segments[start:end])
        if end >= n:
            break
        overlap_count = max(1, round((end - start) * overlap_fraction))
        start = max(start + 1, end - overlap_count)

    return chunks
