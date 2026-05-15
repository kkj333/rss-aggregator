"""RSS の異常な公開日時（例: 2100年）を正規化する。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# フィードのタイムゾーンずれ・予約投稿を許容しつつ、明らかな未来日付を除外する上限
_MAX_PUBLISHED_AT_FUTURE_SKEW = timedelta(days=14)


def sane_published_at(
    published_at: datetime,
    collected_at: datetime,
    *,
    reference_now: datetime | None = None,
) -> datetime:
    """公開日時が現実的な未来を超える場合は collected_at に置き換える。

    RSS が誤った年（例 2100）を返すと一覧の新着順が壊れるため、収集時・読み出し時に利用する。
    """
    now = reference_now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=UTC)
    ceiling = now + _MAX_PUBLISHED_AT_FUTURE_SKEW
    if published_at > ceiling:
        return collected_at
    return published_at
