"""Cloud Run Job エントリポイント（採点）。

Cloud Scheduler から Jobs API で起動される。HTTP エンドポイントは持たない。
収集 Job 完了後に実行する前提で、Firestore の未採点記事を Gemini でスコアリングする。

Exit code:
    0  採点成功（一部記事のエラーは警告ログのみ）
    1  致命的エラー（ストア接続失敗など）
"""

from __future__ import annotations

import json
import logging
import sys

from shared.config import get_settings
from shared.storage import create_classifier_store

from classify.scorer import ArticleScorer

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s\t%(name)s\t%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()

    if not settings.firestore_project:
        logger.error("GOOGLE_CLOUD_PROJECT is required for the classifier job")
        sys.exit(1)

    store = create_classifier_store(
        firestore_project=settings.firestore_project,
        firestore_collection=settings.firestore_collection,
    )

    scorer = ArticleScorer(
        project=settings.firestore_project,
        location=settings.gemini_location,
        model=settings.gemini_model,
    )

    articles = store.list_unclassified(limit=settings.classify_batch_size)
    logger.info("Unclassified articles to score: %d", len(articles))

    scored = 0
    failed = 0
    for article in articles:
        try:
            result = scorer.score(title=article.title, summary=article.summary)
            store.update_classification(
                article_id=article.id,
                relevance_score=result.relevance_score,
                classified_at=result.classified_at,
                classifier_version=result.classifier_version,
            )
            scored += 1
            logger.debug(
                "Scored article %s: %.3f (%s)",
                article.id,
                result.relevance_score,
                article.title[:60],
            )
        except Exception:
            failed += 1
            logger.exception("Failed to score article %s (%s)", article.id, article.title[:60])

    stats = {
        "total": len(articles),
        "scored": scored,
        "failed": failed,
    }
    print(json.dumps(stats, ensure_ascii=False))
    logger.info(
        "Classification complete: total=%d scored=%d failed=%d",
        stats["total"],
        stats["scored"],
        stats["failed"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in classifier job")
        sys.exit(1)
