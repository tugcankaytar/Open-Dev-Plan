"""Runtime-changeable settings (currently just the active model).

Separate from `odp.config.Settings` (env/`.env`-driven process defaults):
a row here, when present, overrides the corresponding config default until
the user changes it again from the UI. Lets a model switch made in the
sidebar apply immediately without an app restart or editing `.env`.
"""

from __future__ import annotations

import sqlite3

from odp.models.time import utc_now_iso

ACTIVE_MODEL_KEY = "active_model"


class AppSettingsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, utc_now_iso()),
        )

    def get_active_model(self, fallback: str) -> str:
        return self.get(ACTIVE_MODEL_KEY) or fallback
