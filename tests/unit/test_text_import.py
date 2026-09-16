from __future__ import annotations

from odp.services.transcription.text_import import build_segments, parse_pasted_transcript


def test_parse_pasted_transcript_detects_speaker_lines():
    text = "Ayşe: Merhaba herkese.\nSadece not, konuşmacı yok.\nMehmet: Ben de buradayım."
    pairs = parse_pasted_transcript(text)
    assert pairs == [
        ("Ayşe", "Merhaba herkese."),
        (None, "Sadece not, konuşmacı yok."),
        ("Mehmet", "Ben de buradayım."),
    ]


def test_parse_pasted_transcript_drops_blank_lines():
    pairs = parse_pasted_transcript("Ayşe: Merhaba\n\n\nMehmet: Selam")
    assert len(pairs) == 2


def test_build_segments_assigns_sequential_seq_and_speaker(tmp_path):
    segments = build_segments("m1", "Ayşe: Merhaba\nMehmet: Selam")
    assert [s.seq for s in segments] == [0, 1]
    assert segments[0].speaker == "Ayşe"
    assert segments[0].meeting_id == "m1"
    assert segments[1].start_ms > segments[0].start_ms


def test_build_segments_respects_start_seq_offset():
    segments = build_segments("m1", "Tek satır", start_seq=5)
    assert segments[0].seq == 5
