"""Manual transcript entry — paste text, get `TranscriptSegment` rows.

A stand-in for the real audio -> faster-whisper pipeline (plan slice 2,
not yet built): lets the extraction pipeline be exercised end-to-end
today from typed or copy-pasted meeting notes, with the same segment
shape (and therefore the same provenance/playback-position semantics)
real transcription will eventually produce.
"""

from __future__ import annotations

import re

from odp.models import TranscriptSegment

_SPEAKER_LINE = re.compile(r"^\s*([^:\n]{1,40}):\s+(.+)$")
_MS_PER_LINE = 4000  # synthetic spacing; no real audio timestamps to anchor to


def parse_pasted_transcript(text: str) -> list[tuple[str | None, str]]:
    """Split raw text into (speaker, line) pairs.

    A line matching "Name: rest of line" is attributed to `Name`; any
    other non-empty line has no speaker. Blank lines are dropped.
    """
    pairs: list[tuple[str | None, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _SPEAKER_LINE.match(line)
        if match:
            pairs.append((match.group(1).strip(), match.group(2).strip()))
        else:
            pairs.append((None, line))
    return pairs


def build_segments(meeting_id: str, text: str, *, start_seq: int = 0) -> list[TranscriptSegment]:
    pairs = parse_pasted_transcript(text)
    return [
        TranscriptSegment(
            meeting_id=meeting_id,
            seq=start_seq + i,
            start_ms=i * _MS_PER_LINE,
            end_ms=(i + 1) * _MS_PER_LINE,
            speaker=speaker,
            text=line,
        )
        for i, (speaker, line) in enumerate(pairs)
    ]
