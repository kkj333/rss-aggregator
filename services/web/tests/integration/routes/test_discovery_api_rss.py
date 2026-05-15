"""discovery ルーター: /api/feeds・/rss の結合テスト。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import shared.config
from fastapi.testclient import TestClient
from shared.config import FeedSource
from shared.models import Article
from shared.storage import InMemoryArticleStore

from web import main as app_main

pytestmark = pytest.mark.integration


def test_api_feeds_includes_site_url(monkeypatch) -> None:
    monkeypatch.setattr(
        shared.config,
        "load_feeds",
        lambda: [
            FeedSource(title="A", url="https://a.example/f.xml", site_url="https://a.example/"),
            FeedSource(title="B", url="https://b.example/f.xml"),
        ],
    )
    client = TestClient(app_main.app)
    r = client.get("/api/feeds")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["site_url"] == "https://a.example/"
    assert data[0]["slug"] is None
    assert data[1]["site_url"] is None
    assert data[1]["slug"] is None


def test_rss_feed_lists_articles_with_original_links(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "テストフィード")
    store = InMemoryArticleStore()
    now = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    store.upsert_many(
        [
            Article(
                id="a1",
                source_title="源ブログ",
                feed_url="https://example.com/feed.xml",
                title="記事タイトル & 特殊",
                url="https://example.com/post/1?x=1&y=2",
                summary="要約",
                author=None,
                published_at=now,
                collected_at=now,
                relevance_score=0.9,
                ai_comment="参考になる記事。",
            ),
        ],
    )
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        r = client.get("/rss")
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "application/rss+xml" in ct
        assert "charset=utf-8" in ct
        body = r.text
        assert "<rss " in body
        assert "<channel>" in body
        assert "<title>テストフィード</title>" in body
        assert "<link>http://testserver/blogs</link>" in body
        assert "atom:link" in body
        assert 'rel="self"' in body
        assert "href=\"http://testserver/rss\"" in body
        assert "<item>" in body
        assert "記事タイトル &amp; 特殊" in body
        assert "https://example.com/post/1?x=1&amp;y=2" in body
        assert "源ブログ" in body
    finally:
        app_main.app.dependency_overrides.clear()
