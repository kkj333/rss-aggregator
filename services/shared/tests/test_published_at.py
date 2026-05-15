"""published_at の異常未来日時を正規化するテスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared.published_at import sane_published_at


def test_sane_published_at_keeps_reasonable_dates() -> None:
    collected = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    pub = datetime(2026, 5, 9, tzinfo=UTC)
    assert sane_published_at(pub, collected, reference_now=collected) == pub


def test_sane_published_at_keeps_scheduled_within_skew() -> None:
    collected = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    pub = collected + timedelta(days=10)
    assert sane_published_at(pub, collected, reference_now=collected) == pub


def test_sane_published_at_clamps_absurd_future() -> None:
    collected = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    absurd = datetime(2100, 1, 1, tzinfo=UTC)
    assert sane_published_at(absurd, collected, reference_now=collected) == collected
