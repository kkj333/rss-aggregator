"""about・robots・sitemap・canonical・GA など SEO / メタ周りの結合テスト。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from shared.config import load_feeds
from shared.storage import InMemoryArticleStore

from web import main as app_main
from web.blog.paths import blog_path_segment

pytestmark = pytest.mark.integration


def test_about_page() -> None:
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        page = client.get("/about")
        assert page.status_code == 200
        assert ">About</a>" in page.text
        assert 'rel="canonical" href="http://testserver/about"' in page.text
        assert 'rel="alternate"' in page.text and "application/rss+xml" in page.text
        assert 'href="/"' in page.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_robots_txt_and_sitemap_xml() -> None:
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        robots = client.get("/robots.txt")
        assert robots.status_code == 200
        assert "User-agent:" in robots.text
        assert "Sitemap: http://testserver/sitemap.xml" in robots.text
        assert "Disallow: /api/" in robots.text

        sm = client.get("/sitemap.xml")
        assert sm.status_code == 200
        assert "<urlset " in sm.text
        assert "<loc>http://testserver/</loc>" in sm.text
        assert "<loc>http://testserver/about</loc>" in sm.text
        assert "<loc>http://testserver/blogs</loc>" in sm.text
        # feeds.json の各ブログ個別ページが含まれる
        feeds = load_feeds()
        assert len(feeds) > 0
        for feed in feeds:
            assert f"<loc>http://testserver/blogs/{blog_path_segment(feed)}</loc>" in sm.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_public_base_url_used_for_seo_urls(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://rss-aggregator.example")
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        page = client.get("/")
        assert page.status_code == 200
        assert 'rel="canonical" href="https://rss-aggregator.example/"' in page.text
        assert 'href="https://rss-aggregator.example/rss"' in page.text

        robots = client.get("/robots.txt")
        assert "Sitemap: https://rss-aggregator.example/sitemap.xml" in robots.text

        sm = client.get("/sitemap.xml")
        assert "<loc>https://rss-aggregator.example/</loc>" in sm.text
        assert "<loc>https://rss-aggregator.example/about</loc>" in sm.text
        assert "<loc>https://rss-aggregator.example/blogs</loc>" in sm.text

        about = client.get("/about")
        assert 'rel="canonical" href="https://rss-aggregator.example/about"' in about.text

        rss = client.get("/rss")
        assert "<link>https://rss-aggregator.example/blogs</link>" in rss.text
        assert 'href="https://rss-aggregator.example/rss"' in rss.text
    finally:
        app_main.app.dependency_overrides.clear()


def test_html_pages_omit_gtag_when_ga_measurement_id_unset(monkeypatch) -> None:
    monkeypatch.delenv("GA_MEASUREMENT_ID", raising=False)
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        for path in ("/", "/about", "/blogs"):
            assert "googletagmanager.com/gtag/js" not in client.get(path).text
    finally:
        app_main.app.dependency_overrides.clear()


def test_html_pages_include_gtag_when_ga_measurement_id_set(monkeypatch) -> None:
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    store = InMemoryArticleStore()
    app_main.app.dependency_overrides[app_main.get_store] = lambda: store

    try:
        client = TestClient(app_main.app)
        for path in ("/", "/about", "/blogs"):
            text = client.get(path).text
            assert "https://www.googletagmanager.com/gtag/js?id=G-TEST12345" in text
            assert 'gtag(\'config\', "G-TEST12345")' in text
    finally:
        app_main.app.dependency_overrides.clear()
