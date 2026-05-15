"""ArticleCommenter のユニットテスト（Gemini Client をモック）。"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import MagicMock, patch

import pytest

from comment.commenter import ArticleCommenter, CommentResult


class TestArticleCommenter:
    def test_comment_returns_result(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "高配当株投資の実践記録として参考になる内容。"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        with patch("comment.commenter.genai.Client", return_value=mock_client):
            commenter = ArticleCommenter(project="test-project", model="gemini-3-flash-preview")
            result = commenter.comment(
                title="2026年配当金まとめ",
                summary="今年受け取った配当金の合計は30万円でした。",
            )

        assert isinstance(result, CommentResult)
        assert result.ai_comment == "高配当株投資の実践記録として参考になる内容。"
        assert result.commentator_version == "gemini-3-flash-preview"
        assert result.commented_at.tzinfo == UTC
        mock_client.models.generate_content.assert_called_once()

    def test_comment_strips_whitespace(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "  余白あり　"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        with patch("comment.commenter.genai.Client", return_value=mock_client):
            commenter = ArticleCommenter(project="test-project", model="gemini-3-flash-preview")
            result = commenter.comment(title="タイトル", summary="サマリー")

        assert result.ai_comment == "余白あり"

    def test_comment_with_url_includes_body_in_prompt(self):
        """URL が渡され本文取得に成功した場合、プロンプトに本文全文が含まれる。"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "配当再投資で年利7%達成した実践報告。"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        with (
            patch("comment.commenter.genai.Client", return_value=mock_client),
            patch(
                "comment.commenter.fetch_article_text",
                return_value="配当再投資で年利7%を達成しました。詳細は本文参照。",
            ),
        ):
            commenter = ArticleCommenter(project="test-project", model="gemini-3-flash-preview")
            result = commenter.comment(
                title="2026年運用実績",
                summary="年利7%を達成",
                url="https://example.com/article/1",
            )

        contents = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "本文全文" in contents
        assert "配当再投資" in contents
        assert result.ai_comment == "配当再投資で年利7%達成した実践報告。"

    def test_comment_falls_back_to_summary_when_fetch_fails(self):
        """URL が渡されても本文取得失敗時は summary のみのプロンプトになる。"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "サマリーのみで生成したコメント。"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        with (
            patch("comment.commenter.genai.Client", return_value=mock_client),
            patch("comment.commenter.fetch_article_text", return_value=None),
        ):
            commenter = ArticleCommenter(project="test-project", model="gemini-3-flash-preview")
            result = commenter.comment(
                title="記事タイトル",
                summary="本文抜粋",
                url="https://example.com/article/2",
            )

        contents = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "本文全文" not in contents
        assert result.ai_comment == "サマリーのみで生成したコメント。"

    def test_comment_raises_on_empty_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        with patch("comment.commenter.genai.Client", return_value=mock_client):
            commenter = ArticleCommenter(project="test-project", model="gemini-3-flash-preview")
            with pytest.raises(RuntimeError, match="empty response"):
                commenter.comment(title="タイトル", summary="サマリー")

    def test_comment_returns_token_counts_from_usage_metadata(self):
        """usage_metadata が存在する場合、トークン数が CommentResult に反映される。"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "トークン確認用コメント。"
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 120
        mock_usage.candidates_token_count = 30
        mock_usage.total_token_count = 150
        mock_response.usage_metadata = mock_usage
        mock_client.models.generate_content.return_value = mock_response

        with patch("comment.commenter.genai.Client", return_value=mock_client):
            commenter = ArticleCommenter(project="test-project", model="gemini-3-flash-preview")
            result = commenter.comment(title="タイトル", summary="サマリー")

        assert result.prompt_tokens == 120
        assert result.candidates_tokens == 30
        assert result.total_tokens == 150

    def test_comment_single_generate_content_call(self):
        """1 回の comment で generate_content が 1 回だけ呼ばれる。"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "一文コメント"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        with patch("comment.commenter.genai.Client", return_value=mock_client):
            commenter = ArticleCommenter(project="test-project", model="gemini-3-flash-preview")
            result = commenter.comment(title="タイトル", summary="サマリー")

        assert result.ai_comment == "一文コメント"
        assert mock_client.models.generate_content.call_count == 1
