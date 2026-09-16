from __future__ import annotations

import itertools

from odp.models import TranscriptSegment
from odp.services.extraction.chunking import chunk_segments, estimate_tokens, fits_in_single_call


def _segments(n: int, text: str = "Bu bir test cümlesidir ve biraz uzunca yazılmıştır. ") -> list:
    return [
        TranscriptSegment(
            meeting_id="m1", seq=i, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=text
        )
        for i in range(n)
    ]


def test_estimate_tokens_scales_with_length():
    assert estimate_tokens("kısa") < estimate_tokens("kısa " * 100)


def test_fits_in_single_call_true_for_small_transcript():
    segments = _segments(3)
    assert fits_in_single_call(segments, max_tokens=10_000) is True


def test_chunk_segments_returns_single_chunk_when_it_fits():
    segments = _segments(5)
    chunks = chunk_segments(segments, max_tokens=10_000)
    assert len(chunks) == 1
    assert chunks[0] == segments


def test_chunk_segments_splits_long_transcript_with_overlap():
    segments = _segments(200)
    chunks = chunk_segments(segments, max_tokens=200, overlap_fraction=0.2)

    assert len(chunks) > 1
    # Every segment must appear in at least one chunk (no gaps).
    covered_seqs = {s.seq for chunk in chunks for s in chunk}
    assert covered_seqs == {s.seq for s in segments}

    # Consecutive chunks must share at least one segment (the overlap).
    for prev, nxt in itertools.pairwise(chunks):
        prev_ids = {s.id for s in prev}
        next_ids = {s.id for s in nxt}
        assert prev_ids & next_ids, "expected overlap between consecutive chunks"


def test_chunk_segments_empty_input():
    assert chunk_segments([], max_tokens=100) == []
