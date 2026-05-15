"""commentator run.py の統合テスト。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import commentator_run as run_module
import pytest

from comment.commenter import CommentResult


def _make_article(article_id: str = "art001", title: str = "テスト記事") -> MagicMock:
    article = MagicMock()
    article.id = article_id
    article.title = title
    article.summary = "本文抜粋"
    return article


class TestRunMain:
    def test_main_happy_path(self, capsys, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
        monkeypatch.setenv("COMMENTATOR_MODEL", "gemini-3-flash-preview")

        mock_store = MagicMock()
        mock_store.list_uncommented.return_value = [_make_article("a1", "記事A")]

        mock_result = CommentResult(
            ai_comment="有益な投資情報が詰まった記事。",
            commented_at=datetime(2026, 5, 1, tzinfo=UTC),
            commentator_version="gemini-3-flash-preview",
            prompt_tokens=100,
            candidates_tokens=25,
            total_tokens=125,
        )
        mock_commenter = MagicMock()
        mock_commenter.comment.return_value = mock_result

        with (
            patch.object(run_module, "create_commentator_store", return_value=mock_store),
            patch.object(run_module, "ArticleCommenter", return_value=mock_commenter),
        ):
            run_module.main()

        mock_store.update_comment.assert_called_once_with(
            article_id="a1",
            ai_comment="有益な投資情報が詰まった記事。",
            commented_at=mock_result.commented_at,
            commentator_version="gemini-3-flash-preview",
        )
        captured = capsys.readouterr()
        stats = json.loads(captured.out.strip().split("\n")[0])
        assert stats["total"] == 1
        assert stats["commented"] == 1
        assert stats["failed"] == 0
        assert stats["tokens"]["prompt"] == 100
        assert stats["tokens"]["candidates"] == 25
        assert stats["tokens"]["total"] == 125

    def test_main_exits_without_project(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            run_module.main()
        assert exc_info.value.code == 1

    def test_main_continues_on_partial_failure(self, capsys, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

        mock_store = MagicMock()
        mock_store.list_uncommented.return_value = [
            _make_article("a1", "記事A"),
            _make_article("a2", "記事B"),
        ]

        mock_commenter = MagicMock()
        mock_commenter.comment.side_effect = [
            RuntimeError("API error"),
            CommentResult(
                ai_comment="参考になる記事。",
                commented_at=datetime(2026, 5, 1, tzinfo=UTC),
                commentator_version="gemini-3-flash-preview",
            ),
        ]

        with (
            patch.object(run_module, "create_commentator_store", return_value=mock_store),
            patch.object(run_module, "ArticleCommenter", return_value=mock_commenter),
        ):
            run_module.main()

        assert mock_store.update_comment.call_count == 1
        captured = capsys.readouterr()
        stats = json.loads(captured.out.strip().split("\n")[0])
        assert stats["total"] == 2
        assert stats["commented"] == 1
        assert stats["failed"] == 1
