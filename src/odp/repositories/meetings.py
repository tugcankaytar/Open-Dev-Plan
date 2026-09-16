"""CRUD for `meetings` and `transcript_segments`."""

from __future__ import annotations

import json
import sqlite3

from odp.models import Meeting, MeetingStatus, TranscriptSegment
from odp.models.time import utc_now_iso


class MeetingsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, meeting: Meeting) -> Meeting:
        now = utc_now_iso()
        meeting.created_at = now
        meeting.updated_at = now
        self._conn.execute(
            """
            INSERT INTO meetings
                (id, project_id, customer_id, title, start_utc, end_utc, timezone, rrule,
                 location_link, participants_json, audio_path, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meeting.id,
                meeting.project_id,
                meeting.customer_id,
                meeting.title,
                meeting.start_utc,
                meeting.end_utc,
                meeting.timezone,
                meeting.rrule,
                meeting.location_link,
                json.dumps(meeting.participants),
                meeting.audio_path,
                meeting.status.value,
                meeting.created_at,
                meeting.updated_at,
            ),
        )
        return meeting

    def get(self, meeting_id: str) -> Meeting | None:
        row = self._conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        return self._row_to_meeting(row) if row else None

    def list_in_range(self, start_utc: str, end_utc: str) -> list[Meeting]:
        """Meetings that overlap [start_utc, end_utc) — the free/busy source of truth."""
        rows = self._conn.execute(
            "SELECT * FROM meetings WHERE status != 'cancelled' "
            "AND start_utc < ? AND end_utc > ? ORDER BY start_utc ASC",
            (end_utc, start_utc),
        ).fetchall()
        return [self._row_to_meeting(row) for row in rows]

    def list_all(self) -> list[Meeting]:
        rows = self._conn.execute("SELECT * FROM meetings ORDER BY start_utc ASC").fetchall()
        return [self._row_to_meeting(row) for row in rows]

    def update_status(self, meeting_id: str, status: MeetingStatus) -> None:
        self._conn.execute(
            "UPDATE meetings SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, utc_now_iso(), meeting_id),
        )

    def update(self, meeting_id: str, **fields: object) -> Meeting | None:
        existing = self.get(meeting_id)
        if existing is None:
            return None
        data = existing.model_dump()
        data.update(fields)
        merged = Meeting.model_validate(data)
        merged.updated_at = utc_now_iso()
        self._conn.execute(
            "UPDATE meetings SET project_id = ?, customer_id = ?, title = ?, start_utc = ?, "
            "end_utc = ?, timezone = ?, rrule = ?, location_link = ?, participants_json = ?, "
            "status = ?, updated_at = ? WHERE id = ?",
            (
                merged.project_id,
                merged.customer_id,
                merged.title,
                merged.start_utc,
                merged.end_utc,
                merged.timezone,
                merged.rrule,
                merged.location_link,
                json.dumps(merged.participants),
                merged.status.value,
                merged.updated_at,
                meeting_id,
            ),
        )
        return self.get(meeting_id)

    def set_audio_path(self, meeting_id: str, audio_path: str) -> None:
        self._conn.execute(
            "UPDATE meetings SET audio_path = ?, updated_at = ? WHERE id = ?",
            (audio_path, utc_now_iso(), meeting_id),
        )

    def delete(self, meeting_id: str) -> None:
        self._conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))

    # --- transcript segments ---

    def add_segments(self, segments: list[TranscriptSegment]) -> None:
        self._conn.executemany(
            "INSERT INTO transcript_segments "
            "(id, meeting_id, seq, start_ms, end_ms, text, speaker, confidence, no_speech_prob) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    s.id,
                    s.meeting_id,
                    s.seq,
                    s.start_ms,
                    s.end_ms,
                    s.text,
                    s.speaker,
                    s.confidence,
                    s.no_speech_prob,
                )
                for s in segments
            ],
        )

    def get_segments(self, meeting_id: str) -> list[TranscriptSegment]:
        rows = self._conn.execute(
            "SELECT * FROM transcript_segments WHERE meeting_id = ? ORDER BY seq ASC",
            (meeting_id,),
        ).fetchall()
        return [self._row_to_segment(row) for row in rows]

    def get_segments_by_ids(self, segment_ids: list[str]) -> list[TranscriptSegment]:
        if not segment_ids:
            return []
        placeholders = ",".join("?" for _ in segment_ids)
        # placeholders is a fixed string of "?" separated by commas, built from the
        # length of segment_ids only — never from user-controlled SQL text.
        query = f"SELECT * FROM transcript_segments WHERE id IN ({placeholders}) ORDER BY seq ASC"
        rows = self._conn.execute(query, segment_ids).fetchall()
        return [self._row_to_segment(row) for row in rows]

    @staticmethod
    def _row_to_meeting(row: sqlite3.Row) -> Meeting:
        return Meeting(
            id=row["id"],
            project_id=row["project_id"],
            customer_id=row["customer_id"],
            title=row["title"],
            start_utc=row["start_utc"],
            end_utc=row["end_utc"],
            timezone=row["timezone"],
            rrule=row["rrule"],
            location_link=row["location_link"],
            participants=json.loads(row["participants_json"]),
            audio_path=row["audio_path"],
            status=MeetingStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_segment(row: sqlite3.Row) -> TranscriptSegment:
        return TranscriptSegment(
            id=row["id"],
            meeting_id=row["meeting_id"],
            seq=row["seq"],
            start_ms=row["start_ms"],
            end_ms=row["end_ms"],
            text=row["text"],
            speaker=row["speaker"],
            confidence=row["confidence"],
            no_speech_prob=row["no_speech_prob"],
        )
