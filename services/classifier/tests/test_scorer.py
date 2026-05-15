"""Unit tests for ArticleScorer (Gemini API はモックする)。"""

from __future__ import annotations

import json
from datetime import UTC
from unittest.mock import MagicMock, patch

import pytest

from classify.scorer import ArticleScorer, ScoreResult


def _make_mock_response(relevance_score: float, reason: str = "テスト") -> MagicMock:
    mock_response = MagicMock()
    mock_response.text = json.dumps({"relevance_score": relevance_score, "reason": reason})
    return mock_response


@pytest.fixture()
def scorer() -> ArticleScorer:
    with patch("classify.scorer.genai.Client"):
        return ArticleScorer(project="test-project")


class TestArticleScorerScore:
    def test_returns_score_result(self, scorer: ArticleScorer) -> None:
        scorer.client.models.generate_content.return_value = _make_mock_response(0.8, "投資記事")

        result = scorer.score(title="配当金を受け取りました", summary="今月の配当は5000円でした。")

        assert isinstance(result, ScoreResult)
        assert result.relevance_score == 0.8
        assert result.reason == "投資記事"
        assert result.classified_at.tzinfo is not None
        assert result.classifier_version == "gemini-3-flash-preview"

    def test_score_clipped_above_one(self, scorer: ArticleScorer) -> None:
        scorer.client.models.generate_content.return_value = _make_mock_response(1.5)

        result = scorer.score(title="株", summary="株の話")

        assert result.relevance_score == 1.0

    def test_score_clipped_below_zero(self, scorer: ArticleScorer) -> None:
        scorer.client.models.generate_content.return_value = _make_mock_response(-0.3)

        result = scorer.score(title="旅行", summary="温泉旅行に行きました")

        assert result.relevance_score == 0.0

    def test_summary_truncated_to_400_chars(self, scorer: ArticleScorer) -> None:
        scorer.client.models.generate_content.return_value = _make_mock_response(0.5)
        long_summary = "x" * 800

        scorer.score(title="テスト", summary=long_summary)

        call_args = scorer.client.models.generate_content.call_args
        prompt: str = call_args.kwargs["contents"]
        assert "x" * 401 not in prompt

    def test_classified_at_is_utc(self, scorer: ArticleScorer) -> None:
        scorer.client.models.generate_content.return_value = _make_mock_response(0.6)

        result = scorer.score(title="テスト", summary="テスト")

        assert result.classified_at.tzinfo == UTC

    def test_reason_defaults_to_empty_string_when_missing(self, scorer: ArticleScorer) -> None:
        mock_response = MagicMock()
        mock_response.text = json.dumps({"relevance_score": 0.5})
        scorer.client.models.generate_content.return_value = mock_response

        result = scorer.score(title="タイトル", summary="本文")

        assert result.reason == ""

    def test_calls_gemini_with_correct_model(self, scorer: ArticleScorer) -> None:
        scorer.client.models.generate_content.return_value = _make_mock_response(0.7)

        scorer.score(title="タイトル", summary="本文")

        call_args = scorer.client.models.generate_content.call_args
        assert call_args.kwargs["model"] == "gemini-3-flash-preview"
