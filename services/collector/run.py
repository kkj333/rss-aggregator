"""Cloud Run Job エントリポイント（RSS 収集）。

Cloud Scheduler から Jobs API で起動される。HTTP エンドポイントは持たない。

Exit code:
    0  収集成功（一部フィードのエラーは警告ログのみ）
    1  致命的エラー（ストア接続失敗など）
"""

from __future__ import annotations

import json
import logging
import sys

from shared.config import get_settings, load_feeds
from shared.storage import create_store

from collect.rss import RSSCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s\t%(name)s\t%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()

    store = create_store(
        firestore_project=settings.firestore_project,
        firestore_collection=settings.firestore_collection,
    )

    feeds = load_feeds()
    logger.info("Starting RSS collection: %d feeds", len(feeds))

    stats = RSSCollector(store=store, feeds=feeds).collect_all()

    print(json.dumps(stats, ensure_ascii=False))

    logger.info(
        "Collection complete: feeds=%d parsed=%d inserted=%d duplicates=%d",
        stats["feeds"],
        stats["parsed"],
        stats["inserted"],
        stats["duplicates"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in collector job")
        sys.exit(1)
