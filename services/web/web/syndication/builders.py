"""canonical / RSS / サイトマップ向けの URL と XML 組み立て。"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any

from fastapi import Request
from shared.config import Settings
from shared.models import Article
from shared.storage import ArticleStore

from web.core.constants import ARTICLE_MAX_DISPLAY, ARTICLE_PAGE_STEP


def public_origin(settings: Settings, request: Request) -> str:
    """canonical / RSS / sitemap 用。本番は PUBLIC_BASE_URL、未設定時はリクエストから。"""
    if settings.public_base_url:
        return str(settings.public_base_url).rstrip("/")
    return str(request.base_url).rstrip("/")


def article_list_context(
    article_store: ArticleStore, display_limit: int, min_score: float | None = None
) -> dict[str, Any]:
    """先頭から display_limit 件を表示し、+1 件取れれば has_more。"""
    display_limit = max(1, min(display_limit, ARTICLE_MAX_DISPLAY))
    fetch_n = min(display_limit + 1, ARTICLE_MAX_DISPLAY + 1)
    rows = article_store.list_latest(fetch_n, min_score=min_score)
    has_more = len(rows) > display_limit
    articles = rows[:display_limit]
    next_limit = min(display_limit + ARTICLE_PAGE_STEP, ARTICLE_MAX_DISPLAY)
    return {
        "articles": articles,
        "has_more": has_more,
        "display_limit": display_limit,
        "next_limit": next_limit,
        "article_max_display": ARTICLE_MAX_DISPLAY,
        "article_page_step": ARTICLE_PAGE_STEP,
    }


def _xml_text(value: str) -> str:
    """RSS 要素テキスト向けに & < > をエスケープする。"""
    return html.escape(value, quote=False)


def sitemap_urlset_xml(*, urls: list[str]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{_xml_text(url)}</loc>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _xml_attr(value: str) -> str:
    """属性値向け（主に atom:link href）。"""
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace("'", "&#39;")
    )


def _pub_date_rfc822(published_at: datetime) -> str:
    dt = published_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return format_datetime(dt.astimezone(UTC), usegmt=True)


def build_rss_xml(
    *,
    channel_title: str,
    channel_link: str,
    channel_description: str,
    feed_self_url: str,
    articles: list[Article],
) -> str:
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{_xml_text(channel_title)}</title>",
        f"    <link>{_xml_text(channel_link)}</link>",
        f"    <description>{_xml_text(channel_description)}</description>",
        "    <language>ja</language>",
        f'    <atom:link href="{_xml_attr(feed_self_url)}" rel="self" type="application/rss+xml"/>',
    ]
    for article in articles:
        desc = f"{article.source_title}: {article.summary}".strip()
        lines.extend(
            [
                "    <item>",
                f"      <title>{_xml_text(article.title)}</title>",
                f"      <link>{_xml_text(article.url)}</link>",
                f'      <guid isPermaLink="true">{_xml_text(article.url)}</guid>',
                f"      <pubDate>{_pub_date_rfc822(article.published_at)}</pubDate>",
                f"      <description>{_xml_text(desc)}</description>",
                "    </item>",
            ],
        )
    lines.extend(["  </channel>", "</rss>"])
    return "\n".join(lines) + "\n"
