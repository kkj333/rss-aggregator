"""GET / と /articles（pages ルーター）の結合テスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from shared.models import Article
from shared.storage import InMemoryArticleStore

from web import main as app_main

pytestmark = pytest.mark.integration


def _articles_for_pagination(count: int) -> list[Article]:
    base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    return [
        Article(
            id=f"id{i}",
            source_title="S",
            feed_url="https://example.com/f.xml",
            title=f"Title {i}",
            url=f"https://example.com/p/{i}",
            summary="",
            author=None,
            published_at=base + timedelta(minutes=i),
            collected_at=base,
            relevance_score=0.9,
            ai_comment="参考になる。",
        )
        for i in range(count)
    ]


def test_index_renders_empty_list_when_no_articles() -> None:
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        page = client.get("/")
        assert page.status_code == 200
        assert "記事はまだありません" in page.text
        assert '<meta name="description" content=' in page.text
        assert 'rel="canonical" href="http://testserver/"' in page.text
        assert 'property="og:url" content="http://testserver/"' in page.text
        assert 'href="http://testserver/rss"' in page.text
        assert 'rel="icon" href="/favicon.ico" sizes="32x32" type="image/png"' in page.text
        assert 'href="/static/favicon.svg" type="image/svg+xml"' in page.text
        assert "/static/styles.css" in page.text
        assert "問い合わせ" not in page.text
        assert 'href="/about"' in page.text
        assert ">About</a>" in page.text
        assert 'href="/blogs"' in page.text
        assert "更新中のサイト" not in page.text

        favicon = client.get("/favicon.ico")
        assert favicon.status_code == 200
        assert favicon.headers.get("content-type", "").startswith("image/png")
        assert favicon.content[:8] == b"\x89PNG\r\n\x1a\n"

        favicon_svg = client.get("/static/favicon.svg")
        assert favicon_svg.status_code == 200
        assert "svg" in favicon_svg.headers.get("content-type", "").lower()
        assert b"<svg" in favicon_svg.content

        css = client.get("/static/styles.css")
        assert css.status_code == 200
        assert css.headers.get("content-type", "").startswith("text/css")
        assert len(css.content) > 0
    finally:
        app_main.app.dependency_overrides.clear()


def test_index_shows_more_button_when_over_fifty_articles() -> None:
    store = InMemoryArticleStore()
    store.upsert_many(_articles_for_pagination(51))
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        page = client.get("/")
        assert page.status_code == 200
        assert "もっと見る" in page.text
        assert 'hx-get="/articles?limit=100"' in page.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_articles_fragment_has_noindex_header() -> None:
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        r = client.get("/articles?limit=50")
        assert r.status_code == 200
        assert r.headers.get("X-Robots-Tag") == "noindex"
    finally:
        app_main.app.dependency_overrides.clear()


def test_articles_fragment_respects_limit_query() -> None:
    store = InMemoryArticleStore()
    store.upsert_many(_articles_for_pagination(80))
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        r = client.get("/articles?limit=100")
        assert r.status_code == 200
        assert r.text.count('class="hn-row"') == 80
        assert "もっと見る" not in r.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_index_shows_only_scored_and_commented_articles(monkeypatch) -> None:
    """評価済み（スコア >= 閾値）かつコメント済みの記事だけを表示する。"""
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0.5")
    store = InMemoryArticleStore()
    now = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    store.upsert_many(
        [
            Article(
                id="hi_commented",
                source_title="S",
                feed_url="https://example.com/f.xml",
                title="投資記事（評価済・コメント済）",
                url="https://example.com/hi",
                summary="",
                author=None,
                published_at=now,
                collected_at=now,
                relevance_score=0.8,
                ai_comment="参考になる記事。",
            ),
            Article(
                id="hi_no_comment",
                source_title="S",
                feed_url="https://example.com/f.xml",
                title="投資記事（評価済・未コメント）",
                url="https://example.com/hi2",
                summary="",
                author=None,
                published_at=now,
                collected_at=now,
                relevance_score=0.8,
                ai_comment=None,
            ),
            Article(
                id="lo",
                source_title="S",
                feed_url="https://example.com/f.xml",
                title="無関係記事",
                url="https://example.com/lo",
                summary="",
                author=None,
                published_at=now,
                collected_at=now,
                relevance_score=0.3,
                ai_comment="コメントあっても低スコア。",
            ),
            Article(
                id="unscored",
                source_title="S",
                feed_url="https://example.com/f.xml",
                title="未採点記事",
                url="https://example.com/unscored",
                summary="",
                author=None,
                published_at=now,
                collected_at=now,
                relevance_score=None,
                ai_comment=None,
            ),
        ]
    )
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        page = client.get("/")
        assert page.status_code == 200
        assert "投資記事（評価済・コメント済）" in page.text
        assert "投資記事（評価済・未コメント）" not in page.text
        assert "無関係記事" not in page.text
        assert "未採点記事" not in page.text
    finally:
        app_main.app.dependency_overrides.clear()
