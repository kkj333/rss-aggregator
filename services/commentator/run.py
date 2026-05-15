"""Cloud Run Job エントリポイント（AIコメント生成）。

Cloud Scheduler から Jobs API で起動される。HTTP エンドポイントは持たない。
分類 Job 完了後に実行する前提で、Firestore の未コメント記事に一言コメントを生成する。

Exit code:
    0  コメント生成成功（一部記事のエラーは警告ログのみ）
    1  致命的エラー（ストア接続失敗など）
"""

from __future__ import annotations

import json
import logging
import os
import sys

from shared.config import get_settings
from shared.storage import create_commentator_store

from comment.commenter import ArticleCommenter

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s\t%(name)s\t%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    project = settings.firestore_project
    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT is required for the commentator job")
        sys.exit(1)

    # Vertex AI を使うために必要な環境変数を設定する
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.gemini_location)

    store = create_commentator_store(
        firestore_project=project,
        firestore_collection=settings.firestore_collection,
    )

    commenter = ArticleCommenter(
        project=project,
        location=settings.gemini_location,
        model=settings.commentator_model,
    )

    articles = store.list_uncommented(
        min_score=settings.relevance_threshold,
        limit=settings.comment_batch_size,
    )
    logger.info("Articles to comment: %d", len(articles))

    commented = 0
    failed = 0
    total_prompt_tokens = 0
    total_candidates_tokens = 0
    total_tokens = 0
    for article in articles:
        try:
            result = commenter.comment(
                title=article.title,
                summary=article.summary,
                url=article.url,
            )
            store.update_comment(
                article_id=article.id,
                ai_comment=result.ai_comment,
                commented_at=result.commented_at,
                commentator_version=result.commentator_version,
            )
            commented += 1
            total_prompt_tokens += result.prompt_tokens
            total_candidates_tokens += result.candidates_tokens
            total_tokens += result.total_tokens
            logger.debug(
                "Commented article %s: %s",
                article.id,
                article.title[:60],
            )
        except Exception:
            failed += 1
            logger.exception("Failed to comment article %s (%s)", article.id, article.title[:60])

    stats = {
        "total": len(articles),
        "commented": commented,
        "failed": failed,
        "tokens": {
            "prompt": total_prompt_tokens,
            "candidates": total_candidates_tokens,
            "total": total_tokens,
        },
    }
    print(json.dumps(stats, ensure_ascii=False))
    logger.info(
        "Comment generation complete: total=%d commented=%d failed=%d tokens=%d",
        stats["total"],
        stats["commented"],
        stats["failed"],
        total_tokens,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in commentator job")
        sys.exit(1)
