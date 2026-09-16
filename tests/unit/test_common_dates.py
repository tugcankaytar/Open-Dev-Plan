from __future__ import annotations

from datetime import date

import pytest

from odp.services.common.dates import resolve_weekday


def test_resolve_weekday_turkish_name():
    # 2026-09-16 is a Wednesday; "cuma" (Friday) should resolve to 09-18.
    assert resolve_weekday("cuma", date(2026, 9, 16)) == date(2026, 9, 18)


def test_resolve_weekday_english_name_case_insensitive():
    assert resolve_weekday("FRIDAY", date(2026, 9, 16)) == date(2026, 9, 18)


def test_resolve_weekday_wraps_to_next_week():
    # Reference is Friday; asking for "monday" must go to next Monday, not today.
    friday = date(2026, 9, 18)
    assert resolve_weekday("monday", friday) == date(2026, 9, 21)


def test_resolve_weekday_unknown_name_raises():
    with pytest.raises(ValueError, match="unrecognized"):
        resolve_weekday("funday", date(2026, 9, 16))
