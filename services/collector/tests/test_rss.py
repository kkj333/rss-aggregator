import pytest
from shared.config import FeedSource
from shared.storage import InMemoryArticleStore

from collect.rss import RSSCollector, _clean_text, stable_article_id


def test_stable_article_id_ignores_url_fragment() -> None:
    first = stable_article_id("https://example.com/posts/1#comments")
    second = stable_article_id("https://example.com/posts/1")

    assert first == second


def test_clean_text_strips_html_and_compacts_whitespace() -> None:
    html = "<p>サンプル <strong>ブログ</strong></p>\n\n新着"

    assert _clean_text(html) == "サンプル ブログ 新着"


def test_clean_text_unescapes_html_entities() -> None:
    assert _clean_text("A &amp; B&nbsp;C") == "A & B C"


def test_entry_url_rejects_non_http_ids() -> None:
    from collect.rss import _entry_url

    assert _entry_url({"id": "tag:hatena.ne.jp,2006:blog-12345-67890"}) is None
    assert _entry_url({"link": "https://example.com/p/1"}) == "https://example.com/p/1"


def test_collect_all_records_fetch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryArticleStore()
    feed = FeedSource(title="取得失敗フィード", url="https://example.com/f.xml")
    monkeypatch.setattr("collect.rss._download_feed", lambda _f: (None, "HTTP 403"))
    stats = RSSCollector(store, [feed]).collect_all()
    assert stats["feeds"] == 1
    assert stats["parsed"] == 0
    assert stats["inserted"] == 0
    assert stats["feed_details"][0]["error"] == "HTTP 403"


def test_collect_all_records_parse_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryArticleStore()
    feed = FeedSource(title="解析失敗フィード", url="https://example.com/g.xml")
    monkeypatch.setattr("collect.rss._download_feed", lambda _f: (b"<rss />", None))

    def boom(_f: FeedSource, _raw: bytes) -> list:
        raise RuntimeError("parse boom")

    monkeypatch.setattr("collect.rss.articles_from_feed_xml", boom)
    stats = RSSCollector(store, [feed]).collect_all()
    assert stats["parsed"] == 0
    assert stats["feed_details"][0]["error"] == "RSSの解析に失敗しました"


def test_collect_deduplicates_articles_in_store(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import collect.rss as rss_module

    store = InMemoryArticleStore()
    feeds = [
        FeedSource(title="テスト投資ブログ", url="https://example.com/feed.xml"),
    ]
    monkeypatch.setattr(rss_module, "_download_feed", lambda _feed: (b"<rss/>", None))
    monkeypatch.setattr(
        rss_module.feedparser,
        "parse",
        lambda _raw: SimpleNamespace(
            entries=[
                {
                    "title": "高配当株の週次メモ",
                    "link": "https://example.com/articles/high-dividend#comments",
                    "summary": "<p>今週見た銘柄のまとめ</p>",
                    "author": "著者A",
                    "published": "Sat, 02 May 2026 03:00:00 +0900",
                }
            ]
        ),
    )

    first = RSSCollector(store=store, feeds=feeds).collect_all()
    assert first["inserted"] == 1
    assert first["duplicates"] == 0

    second = RSSCollector(store=store, feeds=feeds).collect_all()
    assert second["inserted"] == 0
    assert second["duplicates"] == 1

    assert len(store.list_latest()) == 1
    a = store.list_latest()[0]
    assert a.title == "高配当株の週次メモ"
    assert a.url == "https://example.com/articles/high-dividend"


def test_feed_absurd_future_published_at_uses_collected_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RSS が 2100年などの誤った公開日時を返しても収集日時に正規化する。"""
    from types import SimpleNamespace

    import collect.rss as rss_module

    store = InMemoryArticleStore()
    feeds = [FeedSource(title="未来フィード", url="https://example.com/f.xml")]
    monkeypatch.setattr(rss_module, "_download_feed", lambda _feed: (b"<rss/>", None))
    monkeypatch.setattr(
        rss_module.feedparser,
        "parse",
        lambda _raw: SimpleNamespace(
            entries=[
                {
                    "title": "大河の一滴",
                    "link": "https://example.com/absurd",
                    "published_parsed": (2100, 1, 1, 0, 0, 0, 0, 0, 0),
                }
            ]
        ),
    )

    RSSCollector(store=store, feeds=feeds).collect_all()
    a = store.list_latest(limit=5)[0]
    assert a.title == "大河の一滴"
    assert a.published_at.year != 2100
    assert abs((a.published_at - a.collected_at).total_seconds()) < 5
