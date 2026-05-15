"""InMemoryArticleStore のテスト。"""

from __future__ import annotations

from datetime import UTC, datetime

from shared.models import Article
from shared.storage import InMemoryArticleStore


def _make_article(
    article_id: str = "id001",
    feed_url: str = "https://example.com/feed",
    relevance_score: float | None = None,
    ai_comment: str | None = None,
    commented_at: datetime | None = None,
    commentator_version: str | None = None,
    published_at: datetime | None = None,
) -> Article:
    return Article(
        id=article_id,
        source_title="テストブログ",
        feed_url=feed_url,
        title="記事タイトル",
        url=f"https://example.com/article/{article_id}",
        summary="本文抜粋",
        author=None,
        published_at=published_at or datetime(2026, 1, 1, tzinfo=UTC),
        collected_at=datetime(2026, 1, 2, tzinfo=UTC),
        relevance_score=relevance_score,
        ai_comment=ai_comment,
        commented_at=commented_at,
        commentator_version=commentator_version,
    )


class TestInMemoryArticleStore:
    def test_upsert_and_list_latest(self) -> None:
        store = InMemoryArticleStore()
        store.upsert_many([_make_article("a1"), _make_article("a2")])
        results = store.list_latest(limit=10)
        assert len(results) == 2

    def test_upsert_deduplicates(self) -> None:
        store = InMemoryArticleStore()
        assert store.upsert_many([_make_article("a1")]) == 1
        assert store.upsert_many([_make_article("a1")]) == 0
        assert len(store.list_latest()) == 1

    def test_list_latest_ordered_by_published_at(self) -> None:
        store = InMemoryArticleStore()
        older = _make_article("old", published_at=datetime(2026, 1, 1, tzinfo=UTC))
        newer = _make_article("new", published_at=datetime(2026, 1, 2, tzinfo=UTC))
        store.upsert_many([older, newer])
        results = store.list_latest()
        assert results[0].id == "new"
        assert results[1].id == "old"

    def test_list_latest_with_min_score_filters(self) -> None:
        store = InMemoryArticleStore()
        store.upsert_many([
            _make_article("hi", relevance_score=0.8, ai_comment="good"),
            _make_article("lo", relevance_score=0.3, ai_comment="ok"),
            _make_article("no_comment", relevance_score=0.9, ai_comment=None),
            _make_article("unscored"),
        ])
        results = store.list_latest(min_score=0.5)
        assert len(results) == 1
        assert results[0].id == "hi"

    def test_list_by_feed_filters_by_url(self) -> None:
        store = InMemoryArticleStore()
        store.upsert_many([
            _make_article("a1", feed_url="https://feed-a.example/rss"),
            _make_article("a2", feed_url="https://feed-a.example/rss"),
            _make_article("b1", feed_url="https://feed-b.example/rss"),
        ])
        results = store.list_by_feed("https://feed-a.example/rss")
        assert len(results) == 2
        assert all(a.feed_url == "https://feed-a.example/rss" for a in results)

    def test_roundtrip_with_ai_comment(self) -> None:
        now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
        store = InMemoryArticleStore()
        store.upsert_many([_make_article(
            relevance_score=0.9,
            ai_comment="長期投資の実績報告。参考になる。",
            commented_at=now,
            commentator_version="gemini-3-flash-preview",
        )])
        stored = store.list_latest()[0]
        assert stored.ai_comment == "長期投資の実績報告。参考になる。"
        assert stored.commented_at == now
        assert stored.commentator_version == "gemini-3-flash-preview"

    def test_roundtrip_without_ai_comment(self) -> None:
        store = InMemoryArticleStore()
        store.upsert_many([_make_article(relevance_score=0.8)])
        stored = store.list_latest()[0]
        assert stored.ai_comment is None
        assert stored.commented_at is None
        assert stored.commentator_version is None
