from __future__ import annotations

from datetime import UTC, datetime

import pytest

from odp.models.time import from_utc_iso, to_utc_iso, utc_now_iso


def test_utc_now_iso_has_z_suffix():
    assert utc_now_iso().endswith("Z")


def test_to_utc_iso_rejects_naive_datetime():
    with pytest.raises(ValueError, match="naive"):
        to_utc_iso(datetime(2026, 9, 22, 10, 30))


def test_round_trip():
    dt = datetime(2026, 9, 22, 10, 30, tzinfo=UTC)
    s = to_utc_iso(dt)
    assert s == "2026-09-22T10:30:00Z"
    assert from_utc_iso(s) == dt
