"""/blogs・/feeds リダイレクト・/blogs/{id} の結合テスト（TestClient）。"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
import shared.config
from fastapi.testclient import TestClient
from shared.config import FeedSource
from shared.models import Article
from shared.storage import InMemoryArticleStore

import web.routes.pages as pages_mod
from web import main as app_main
from web.blog.paths import compute_feed_id

pytestmark = pytest.mark.integration


def _fake_feed_sources(n: int) -> list[FeedSource]:
    return [FeedSource(title=f"F{i}", url=f"https://e.example/{i}.xml") for i in range(n)]


def test_blogs_list_paginates(monkeypatch) -> None:
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(25))

    client = TestClient(app_main.app)
    p1 = client.get("/blogs")
    assert p1.status_code == 200
    assert "F0" in p1.text
    assert "F19" in p1.text
    assert "F20" not in p1.text
    assert 'href="/blogs?page=2"' in p1.text
    assert 'rel="canonical" href="http://testserver/blogs"' in p1.text

    p2 = client.get("/blogs?page=2")
    assert p2.status_code == 200
    assert "F20" in p2.text
    assert "F24" in p2.text
    assert 'href="/blogs?page=1"' in p2.text
    assert 'rel="canonical" href="http://testserver/blogs?page=2"' in p2.text


def test_blogs_list_page_out_of_range_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(25))
    client = TestClient(app_main.app)
    assert client.get("/blogs?page=3").status_code == 404


def test_blogs_list_empty(monkeypatch) -> None:
    monkeypatch.setattr(shared.config, "load_feeds", lambda: [])
    client = TestClient(app_main.app)
    r = client.get("/blogs")
    assert r.status_code == 200
    assert "まとめている掲載元サイトは、まだありません。" in r.text


def test_blogs_list_links_only_to_blog_detail_not_homepage_or_feed_xml(monkeypatch) -> None:
    """一覧ではブログ名→当サイトの個別ページのみ。外部のホーム・RSS URLは出さない。"""
    feed_url = "https://example.com/feed.xml"
    segment = compute_feed_id(feed_url)
    monkeypatch.setattr(
        shared.config,
        "load_feeds",
        lambda: [
            FeedSource(
                title="Blog A",
                url=feed_url,
                site_url="https://example.com/",
            ),
        ],
    )
    client = TestClient(app_main.app)
    page = client.get("/blogs")
    assert page.status_code == 200
    assert f'href="/blogs/{segment}"' in page.text
    assert "Blog A" in page.text
    assert "ホームページ" not in page.text
    assert "RSS フィード" not in page.text
    assert 'href="https://example.com/"' not in page.text
    assert 'href="https://example.com/feed.xml"' not in page.text


def test_feeds_redirects_to_blogs(monkeypatch) -> None:
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(1))
    client = TestClient(app_main.app, follow_redirects=False)
    r = client.get("/feeds")
    assert r.status_code == 301
    assert r.headers["location"] == "/blogs"


def test_feeds_redirects_to_blogs_with_page(monkeypatch) -> None:
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(25))
    client = TestClient(app_main.app, follow_redirects=False)
    r = client.get("/feeds?page=2")
    assert r.status_code == 301
    assert r.headers["location"] == "/blogs?page=2"


def test_blog_detail_invalid_feed_id_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(1))
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store
    try:
        client = TestClient(app_main.app)
        assert client.get("/blogs/notvalid").status_code == 404
        assert client.get("/blogs/" + "a" * 63).status_code == 404
        assert client.get("/blogs/" + "z" * 64).status_code == 404
    finally:
        app_main.app.dependency_overrides.clear()


def test_blog_detail_unknown_feed_id_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(1))
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store
    try:
        client = TestClient(app_main.app)
        assert client.get("/blogs/" + "a" * 64).status_code == 404
    finally:
        app_main.app.dependency_overrides.clear()


def test_blog_detail_known_feed_returns_200(monkeypatch) -> None:
    feed_url = "https://e.example/0.xml"
    feed_id = hashlib.sha256(feed_url.encode()).hexdigest()
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(1))
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store
    try:
        client = TestClient(app_main.app)
        r = client.get(f"/blogs/{feed_id}")
        assert r.status_code == 200
        assert "F0" in r.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_blog_detail_shows_firestore_profile(monkeypatch) -> None:
    feed_url = "https://e.example/0.xml"
    feed_id = hashlib.sha256(feed_url.encode()).hexdigest()
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(1))
    monkeypatch.setattr(
        pages_mod,
        "get_feed_profile",
        lambda _fid: "Profiler が書いた紹介プロフィール",
    )
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store
    try:
        client = TestClient(app_main.app)
        r = client.get(f"/blogs/{feed_id}")
        assert r.status_code == 200
        assert "Profiler が書いた紹介プロフィール" in r.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_blog_detail_by_slug_returns_200(monkeypatch) -> None:
    monkeypatch.setattr(
        shared.config,
        "load_feeds",
        lambda: [
            FeedSource(
                title="Sluggy",
                url="https://e.example/0.xml",
                slug="my-feed",
                site_url="https://publisher.example/",
            ),
        ],
    )
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store
    try:
        client = TestClient(app_main.app)
        r = client.get("/blogs/my-feed")
        assert r.status_code == 200
        assert "Sluggy" in r.text
        assert "ホームページ" not in r.text
        assert "RSS フィード" not in r.text
        assert 'href="https://publisher.example/"' not in r.text
        assert 'href="https://e.example/0.xml"' not in r.text
        assert 'rel="canonical" href="http://testserver/blogs/my-feed"' in r.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_blog_detail_legacy_hex_redirects_to_slug(monkeypatch) -> None:
    feed_url = "https://e.example/0.xml"
    feed_id = hashlib.sha256(feed_url.encode()).hexdigest()
    monkeypatch.setattr(
        shared.config,
        "load_feeds",
        lambda: [
            FeedSource(title="Sluggy", url=feed_url, slug="my-feed"),
        ],
    )
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store
    try:
        client = TestClient(app_main.app, follow_redirects=False)
        r = client.get(f"/blogs/{feed_id}")
        assert r.status_code == 301
        assert r.headers["location"] == "/blogs/my-feed"
    finally:
        app_main.app.dependency_overrides.clear()


def test_blog_detail_shows_only_articles_for_feed(monkeypatch) -> None:
    feed_url = "https://e.example/0.xml"
    other_feed_url = "https://e.example/1.xml"
    feed_id = hashlib.sha256(feed_url.encode()).hexdigest()
    monkeypatch.setattr(shared.config, "load_feeds", lambda: _fake_feed_sources(2))
    store = InMemoryArticleStore()
    now = datetime(2024, 1, 1, tzinfo=UTC)
    store.upsert_many(
        [
            Article(
                id="a1",
                source_title="F0",
                feed_url=feed_url,
                title="Feed 0 Article",
                url="https://e.example/0/1",
                summary="",
                author=None,
                published_at=now,
                collected_at=now,
                relevance_score=0.9,
                ai_comment="good",
            ),
            Article(
                id="a2",
                source_title="F1",
                feed_url=other_feed_url,
                title="Feed 1 Article",
                url="https://e.example/1/1",
                summary="",
                author=None,
                published_at=now,
                collected_at=now,
                relevance_score=0.9,
                ai_comment="good",
            ),
        ]
    )
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store
    try:
        client = TestClient(app_main.app)
        r = client.get(f"/blogs/{feed_id}")
        assert r.status_code == 200
        assert "Feed 0 Article" in r.text
        assert "Feed 1 Article" not in r.text
    finally:
        app_main.app.dependency_overrides.clear()
