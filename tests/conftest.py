"""Shared test fixtures.

Includes the network-ban fixture from plan §8: the app's core promise is
that data never leaves the device, so tests fail loudly if any code path
tries to open a socket to anything but localhost.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from odp.config import Settings
from odp.db import open_db

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_real_create_connection = socket.create_connection


def _guarded_create_connection(address: tuple, *args: object, **kwargs: object) -> socket.socket:
    host = address[0] if isinstance(address, tuple) else address
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"Blocked outbound connection to {host!r} in tests — Open-Dev-Plan must never "
            "phone home. If this is a legitimate localhost service, add it to _LOCAL_HOSTS."
        )
    return _real_create_connection(address, *args, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "create_connection", _guarded_create_connection)


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", config_dir=tmp_path / "config")


@pytest.fixture
def db_conn(tmp_settings: Settings):
    tmp_settings.ensure_dirs()
    conn = open_db(tmp_settings.db_path)
    yield conn
    conn.close()
