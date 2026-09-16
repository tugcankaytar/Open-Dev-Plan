from __future__ import annotations

from odp.repositories.app_settings import AppSettingsRepository


def test_get_returns_none_when_unset(db_conn):
    repo = AppSettingsRepository(db_conn)
    assert repo.get("active_model") is None


def test_set_then_get_round_trips(db_conn):
    repo = AppSettingsRepository(db_conn)
    repo.set("active_model", "gpt-oss:20b")
    assert repo.get("active_model") == "gpt-oss:20b"


def test_set_overwrites_existing_value(db_conn):
    repo = AppSettingsRepository(db_conn)
    repo.set("active_model", "gpt-oss:20b")
    repo.set("active_model", "qwen3:14b")
    assert repo.get("active_model") == "qwen3:14b"


def test_get_active_model_falls_back_when_unset(db_conn):
    repo = AppSettingsRepository(db_conn)
    assert repo.get_active_model("gpt-oss:20b") == "gpt-oss:20b"


def test_get_active_model_prefers_stored_value(db_conn):
    repo = AppSettingsRepository(db_conn)
    repo.set("active_model", "qwen3:14b")
    assert repo.get_active_model("gpt-oss:20b") == "qwen3:14b"
