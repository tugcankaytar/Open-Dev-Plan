from __future__ import annotations

from datetime import UTC, datetime

import pytest

from odp.models.time import from_utc_iso, normalize_utc_iso, to_utc_iso, utc_now_iso


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


def test_from_utc_iso_accepts_browser_millisecond_timestamps():
    # `Date.toISOString()` in JS always emits milliseconds — every form
    # created through the web UI arrives shaped like this, so parsing it
    # must not crash (this exact string broke the scheduler live before
    # from_utc_iso() was made tolerant of fractional seconds).
    dt = from_utc_iso("2026-09-17T19:00:00.000Z")
    assert dt == datetime(2026, 9, 17, 19, 0, 0, tzinfo=UTC)


def test_normalize_utc_iso_strips_milliseconds():
    assert normalize_utc_iso("2026-09-17T19:00:00.123Z") == "2026-09-17T19:00:00Z"


def test_normalize_utc_iso_is_idempotent_on_our_own_format():
    assert normalize_utc_iso("2026-09-17T19:00:00Z") == "2026-09-17T19:00:00Z"
