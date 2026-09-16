"""SQLite connection + migration runner.

Single-file, WAL-mode SQLite is our entire persistence layer (plan §1/#3):
no server process, no partial-write corruption risk, and free FTS5 +
sqlite-vec support in the same file. Migrations are plain numbered .sql
files applied in order, tracked via ``PRAGMA user_version`` — no ORM.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlite_vec  # type: ignore[import-untyped]

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_RE = re.compile(r"^(\d{4})_.*\.sql$")


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    return conn


def _pending_migrations(current_version: int) -> list[tuple[int, Path]]:
    found: list[tuple[int, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = _MIGRATION_RE.match(path.name)
        if not m:
            continue
        version = int(m.group(1))
        if version > current_version:
            found.append((version, path))
    found.sort(key=lambda t: t[0])
    return found


def migrate(conn: sqlite3.Connection) -> int:
    """Apply any migration files newer than the DB's current user_version.

    Returns the resulting schema version. Safe to call on every startup.
    """
    current: int = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, path in _pending_migrations(current):
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(f"PRAGMA user_version = {version}")
        current = version
    return current


def open_db(db_path: Path) -> sqlite3.Connection:
    """Open (creating if needed) and migrate the application database."""
    conn = _connect(db_path)
    migrate(conn)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Wrap a block of writes in a single transaction (all-or-nothing)."""
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
