"""Article モデルのテスト。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shared.models import Article


def _base_article(**kwargs) -> Article:
    defaults = dict(
        id="abc123",
        source_title="テストブログ",
        feed_url="https://example.com/feed",
        title="テスト記事タイトル",
        url="https://example.com/article/1",
        summary="本文抜粋",
        author=None,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        collected_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return Article(**defaults)


class TestArticleDefaults:
    def test_classifier_fields_default_to_none(self):
        article = _base_article()
        assert article.relevance_score is None
        assert article.classified_at is None
        assert article.classifier_version is None

    def test_commentator_fields_default_to_none(self):
        article = _base_article()
        assert article.ai_comment is None
        assert article.commented_at is None
        assert article.commentator_version is None


class TestArticleWithCommentatorFields:
    def test_ai_comment_stored(self):
        now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
        article = _base_article(
            ai_comment="高配当株への投資実績をまとめた有益な記事。",
            commented_at=now,
            commentator_version="gemini-3-flash-preview",
        )
        assert article.ai_comment == "高配当株への投資実績をまとめた有益な記事。"
        assert article.commented_at == now
        assert article.commentator_version == "gemini-3-flash-preview"

    def test_article_is_frozen(self):
        article = _base_article()
        with pytest.raises((AttributeError, TypeError)):
            article.ai_comment = "変更不可"  # type: ignore[misc]
