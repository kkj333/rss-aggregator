"""Integration-style tests for run.main() — ストア・スコアラーはすべてモック。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from shared.models import Article

from classify.scorer import ScoreResult


def _make_article(article_id: str = "abc123") -> Article:
    now = datetime.now(UTC)
    return Article(
        id=article_id,
        source_title="テストブログ",
        feed_url="https://example.com/feed",
        title="配当金レポート",
        url=f"https://example.com/{article_id}",
        summary="今月の配当は5000円でした。",
        author=None,
        published_at=now,
        collected_at=now,
    )


def _make_score_result(score: float = 0.8) -> ScoreResult:
    return ScoreResult(
        relevance_score=score,
        reason="投資関連",
        classified_at=datetime.now(UTC),
        classifier_version="gemini-3-flash-preview",
    )


@pytest.fixture()
def mock_settings():
    settings = MagicMock()
    settings.firestore_project = "test-project"
    settings.firestore_collection = "articles"
    settings.gemini_location = "global"
    settings.gemini_model = "gemini-3-flash-preview"
    settings.classify_batch_size = 100
    return settings


class TestMain:
    def test_main_logs_stats_without_error(self, mock_settings, capsys) -> None:
        """logger.info に stats を渡す際に TypeError が発生しないことを確認する。"""
        article = _make_article()
        mock_store = MagicMock()
        mock_store.list_unclassified.return_value = [article]
        mock_scorer = MagicMock()
        mock_scorer.score.return_value = _make_score_result(0.8)

        with (
            patch("run.get_settings", return_value=mock_settings),
            patch("run.create_classifier_store", return_value=mock_store),
            patch("run.ArticleScorer", return_value=mock_scorer),
        ):
            from run import main

            main()

        captured = capsys.readouterr()
        import json

        stats = json.loads(captured.out)
        assert stats["total"] == 1
        assert stats["scored"] == 1
        assert stats["failed"] == 0

    def test_main_counts_failed_when_scorer_raises(self, mock_settings, capsys) -> None:
        article = _make_article()
        mock_store = MagicMock()
        mock_store.list_unclassified.return_value = [article]
        mock_scorer = MagicMock()
        mock_scorer.score.side_effect = RuntimeError("Gemini error")

        with (
            patch("run.get_settings", return_value=mock_settings),
            patch("run.create_classifier_store", return_value=mock_store),
            patch("run.ArticleScorer", return_value=mock_scorer),
        ):
            from run import main

            main()

        captured = capsys.readouterr()
        import json

        stats = json.loads(captured.out)
        assert stats["failed"] == 1
        assert stats["scored"] == 0

    def test_main_exits_1_when_no_project(self, mock_settings) -> None:
        mock_settings.firestore_project = None

        with (
            patch("run.get_settings", return_value=mock_settings),
            pytest.raises(SystemExit) as exc_info,
        ):
            from run import main

            main()

        assert exc_info.value.code == 1
