from __future__ import annotations

from odp.db import migrate, open_db


def test_migrate_applies_and_is_idempotent(tmp_settings):
    tmp_settings.ensure_dirs()
    conn = open_db(tmp_settings.db_path)
    try:
        version_after_open = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version_after_open >= 1

        # Re-running migrate() on an already-current DB must be a no-op.
        version_again = migrate(conn)
        assert version_again == version_after_open

        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        tables = {row[0] for row in rows}
        for expected in [
            "projects",
            "meetings",
            "transcript_segments",
            "tasks",
            "task_dependencies",
            "proposals",
            "jobs",
            "prompt_cache",
            "training_examples",
        ]:
            assert expected in tables
    finally:
        conn.close()


def test_wal_and_foreign_keys_enabled(db_conn):
    assert db_conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert db_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_fts_search_follows_segment_inserts(db_conn):
    now = "2026-09-16T12:00:00Z"
    db_conn.execute(
        "INSERT INTO meetings (id, title, start_utc, end_utc, timezone, created_at, updated_at) "
        "VALUES ('m1', 'Test', ?, ?, 'Europe/Istanbul', ?, ?)",
        (now, now, now, now),
    )
    db_conn.execute(
        "INSERT INTO transcript_segments (id, meeting_id, seq, start_ms, end_ms, text) "
        "VALUES ('s1', 'm1', 0, 0, 1000, 'bütçe konusunda karar aldık')",
    )
    rows = db_conn.execute(
        "SELECT ts.id FROM transcript_segments_fts fts "
        "JOIN transcript_segments ts ON ts.rowid = fts.rowid "
        "WHERE transcript_segments_fts MATCH 'bütçe'"
    ).fetchall()
    assert [r[0] for r in rows] == ["s1"]
