"""Cloud Run Job エントリポイント（ブログプロファイル生成）。

Cloud Scheduler から Jobs API で起動される。HTTP エンドポイントは持たない。
feeds.json の各ブログについて Google ADK（web 検索付き）でプロフィールを生成し、
Firestore の feeds コレクションに書き込む。

Exit code:
    0  完了（一部フィードのエラーは警告ログのみ）
    1  致命的エラー（設定不足など）
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys

from shared.config import get_settings, load_feeds

from feed_profiler.style_profiler import FeedProfiler

_debug = os.getenv("PROFILER_DEBUG", "").lower() in ("1", "true", "yes")
logging.basicConfig(
    level=logging.DEBUG if _debug else logging.INFO,
    format="%(levelname)s\t%(name)s\t%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_FIRESTORE_PROFILE_FIELD = "profile"


def _compute_feed_id(feed_url: str) -> str:
    return hashlib.sha256(feed_url.encode("utf-8")).hexdigest()


def _get_firestore_client(project: str):  # type: ignore[return]
    from google.cloud import firestore  # type: ignore[import-untyped]

    return firestore.Client(project=project)


def _has_existing_profile(client, collection: str, feed_id: str) -> bool:
    doc = client.collection(collection).document(feed_id).get()
    if not doc.exists:
        return False
    data = doc.to_dict() or {}
    return bool((data.get(_FIRESTORE_PROFILE_FIELD) or "").strip())


def _write_profile(
    client, collection: str, feed_id: str, feed_url: str, feed_title: str,
    site_url: str | None, result,
) -> None:
    doc_data = {
        "title": feed_title,
        "feed_url": feed_url,
        "site_url": site_url,
        "profile": result.profile,
        "investment_style": result.investment_style,
        "sources": result.sources,
        "profiled_at": result.profiled_at,
        "profiler_version": result.profiler_version,
    }
    client.collection(collection).document(feed_id).set(doc_data, merge=True)


def main() -> None:
    settings = get_settings()
    project = settings.firestore_project
    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT is required for the profiler job")
        sys.exit(1)

    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.gemini_location)

    feeds = load_feeds()
    logger.info("Feeds to process: %d", len(feeds))

    client = _get_firestore_client(project)
    collection = settings.firestore_feeds_collection
    profiler = FeedProfiler(
        project=project,
        location=settings.gemini_location,
        model=settings.profiler_model,
    )

    updated = 0
    skipped = 0
    failed = 0

    for feed in feeds:
        feed_id = _compute_feed_id(feed.url)
        try:
            if settings.profiler_skip_existing and _has_existing_profile(
                client, collection, feed_id
            ):
                logger.info("Skip (existing profile): %s", feed.title)
                skipped += 1
                continue

            logger.info("Profiling: %s (site_url=%s)", feed.title, feed.site_url)
            result = profiler.profile(title=feed.title, site_url=feed.site_url)
            _write_profile(client, collection, feed_id, feed.url, feed.title, feed.site_url, result)
            updated += 1
            logger.info(
                "  -> styles=%s  sources=%d  profile=%d chars",
                result.investment_style,
                len(result.sources),
                len(result.profile),
            )
        except Exception:
            failed += 1
            logger.exception("Failed to profile feed: %s", feed.title)

    stats = {
        "feeds_total": len(feeds),
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }
    print(json.dumps(stats, ensure_ascii=False))
    logger.info(
        "Profiling complete: total=%d updated=%d skipped=%d failed=%d",
        len(feeds),
        updated,
        skipped,
        failed,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in profiler job")
        sys.exit(1)
