from __future__ import annotations

import hashlib
import html
import logging
import re
from calendar import timegm
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urlparse
from urllib.request import Request, urlopen

import feedparser
from shared.config import FeedSource
from shared.models import Article
from shared.published_at import sane_published_at
from shared.storage import ArticleStore

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

logger = logging.getLogger(__name__)

DEFAULT_FEED_TIMEOUT_SEC = 30
DEFAULT_FEED_ACCEPT = (
    "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1"
)
# 一部サイトがシンプルな UA を拒むため、一般的なブラウザに近い文字列にする
DEFAULT_FEED_USER_AGENT = "Mozilla/5.0 (compatible; rss-aggregator/0.1; RSS reader)"


class FeedDetail(TypedDict):
    """フィード1件あたりの収集結果（ログやジョブ出力と共通）。"""

    title: str
    url: str
    parsed: int
    error: str | None


class CollectStats(TypedDict):
    feeds: int
    parsed: int
    inserted: int
    duplicates: int
    feed_details: list[FeedDetail]


class RSSCollector:
    def __init__(self, store: ArticleStore, feeds: list[FeedSource]) -> None:
        self.store = store
        self.feeds = feeds

    def collect_all(self) -> CollectStats:
        parsed_count = 0
        articles: list[Article] = []
        feed_details: list[FeedDetail] = []

        for feed in self.feeds:
            try:
                raw, fetch_error = _download_feed(feed)
                if raw is None:
                    feed_details.append(
                        FeedDetail(
                            title=feed.title,
                            url=feed.url,
                            parsed=0,
                            error=fetch_error or "RSSを取得できませんでした",
                        ),
                    )
                    continue

                feed_articles = articles_from_feed_xml(feed, raw)
                feed_details.append(
                    FeedDetail(
                        title=feed.title,
                        url=feed.url,
                        parsed=len(feed_articles),
                        error=None,
                    ),
                )
                parsed_count += len(feed_articles)
                articles.extend(feed_articles)
            except Exception:
                logger.exception("Unexpected error while parsing feed %s", feed.url)
                feed_details.append(
                    FeedDetail(
                        title=feed.title,
                        url=feed.url,
                        parsed=0,
                        error="RSSの解析に失敗しました",
                    ),
                )

        inserted = self.store.upsert_many(articles)
        return CollectStats(
            feeds=len(self.feeds),
            parsed=parsed_count,
            inserted=inserted,
            duplicates=parsed_count - inserted,
            feed_details=feed_details,
        )


def parse_feed(feed: FeedSource) -> list[Article]:
    raw, err = _download_feed(feed)
    if raw is None:
        return []
    return articles_from_feed_xml(feed, raw)


def articles_from_feed_xml(feed: FeedSource, raw: bytes) -> list[Article]:
    try:
        parsed = feedparser.parse(raw)
    except Exception:
        logger.exception("feedparser failed for %s", feed.url)
        return []

    collected_at = datetime.now(UTC)

    articles: list[Article] = []
    for entry in parsed.entries:
        url = _entry_url(entry)
        if not url:
            continue

        raw_published = _entry_datetime(entry)
        published_at = sane_published_at(
            raw_published if raw_published is not None else collected_at,
            collected_at,
        )
        if raw_published is not None and published_at != raw_published:
            logger.warning(
                "Clamping absurd RSS published_at %s for %s (using collected_at)",
                raw_published,
                url[:80],
            )
        title = _clean_text(entry.get("title", "無題"))
        summary = _clean_text(entry.get("summary", entry.get("description", "")))
        article_id = stable_article_id(url)

        articles.append(
            Article(
                id=article_id,
                source_title=feed.title,
                feed_url=feed.url,
                title=title,
                url=url,
                summary=summary[:500],
                author=entry.get("author"),
                published_at=published_at,
                collected_at=collected_at,
            )
        )

    return articles


def _download_feed(feed: FeedSource) -> tuple[bytes | None, str | None]:
    ua = feed.user_agent or DEFAULT_FEED_USER_AGENT
    request = Request(
        feed.url,
        headers={
            "User-Agent": ua,
            "Accept": DEFAULT_FEED_ACCEPT,
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=DEFAULT_FEED_TIMEOUT_SEC) as response:
            return response.read(), None
    except HTTPError as exc:
        msg = f"HTTP {exc.code}"
        logger.warning("Feed fetch failed for %s: %s", feed.url, exc)
        return None, msg
    except URLError as exc:
        reason = exc.reason
        msg = str(reason) if reason else "接続エラー"
        logger.warning("Feed fetch failed for %s: %s", feed.url, exc)
        return None, msg
    except (TimeoutError, OSError) as exc:
        logger.warning("Feed fetch failed for %s: %s", feed.url, exc)
        return None, str(exc) or "タイムアウト"


def stable_article_id(url: str) -> str:
    normalized_url, _fragment = urldefrag(url.strip())
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def _entry_url(entry: feedparser.FeedParserDict) -> str | None:
    link = entry.get("link")
    if link and _is_http_url(str(link).strip()):
        normalized_url, _fragment = urldefrag(str(link).strip())
        return normalized_url

    entry_id = entry.get("id")
    if entry_id and _is_http_url(str(entry_id).strip()):
        normalized_url, _fragment = urldefrag(str(entry_id).strip())
        return normalized_url

    return None


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    return bool(parsed.netloc)


def _entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(timegm(value), tz=UTC)

    for key in ("published", "updated"):
        value = entry.get(key)
        if value:
            try:
                parsed = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                continue
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    return None


def _clean_text(value: str) -> str:
    unescaped = html.unescape(value)
    no_tags = TAG_RE.sub(" ", unescaped)
    no_nbsp = no_tags.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", no_nbsp).strip()
