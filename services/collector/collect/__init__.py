"""RSS 収集ジョブ用ロジック（Web パッケージ `app` のストア・モデルを利用）。"""

from collect.rss import (
    CollectStats,
    FeedDetail,
    RSSCollector,
    stable_article_id,
)

__all__ = [
    "RSSCollector",
    "CollectStats",
    "FeedDetail",
    "stable_article_id",
]
