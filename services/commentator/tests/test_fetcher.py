"""comment.fetcher のユニットテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from comment.fetcher import fetch_article_text, is_allowed_by_robots

_SAMPLE_HTML = """\
<!DOCTYPE html>
<html>
<head><title>テスト記事</title></head>
<body>
  <article>
    <p>高配当株を中心に2026年の運用成績をまとめました。</p>
    <p>配当再投資で年利7%を達成できました。</p>
    <script>console.log("ignore me")</script>
  </article>
</body>
</html>
"""


class TestIsAllowedByRobots:
    def test_allowed_when_robots_txt_permits(self):
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = True
        with patch("comment.fetcher.urllib.robotparser.RobotFileParser", return_value=mock_rp):
            assert is_allowed_by_robots("https://example.com/article") is True
        mock_rp.can_fetch.assert_called_once()

    def test_disallowed_when_robots_txt_denies(self):
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False
        with patch("comment.fetcher.urllib.robotparser.RobotFileParser", return_value=mock_rp):
            assert is_allowed_by_robots("https://example.com/article") is False

    def test_allowed_when_robots_txt_unreachable(self):
        mock_rp = MagicMock()
        mock_rp.read.side_effect = OSError("connection refused")
        with patch("comment.fetcher.urllib.robotparser.RobotFileParser", return_value=mock_rp):
            assert is_allowed_by_robots("https://example.com/article") is True


class TestFetchArticleText:
    def test_returns_text_from_article_tag(self):
        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_HTML
        mock_resp.raise_for_status.return_value = None

        with (
            patch("comment.fetcher.is_allowed_by_robots", return_value=True),
            patch("comment.fetcher.httpx.get", return_value=mock_resp),
        ):
            text = fetch_article_text("https://example.com/article/1")

        assert text is not None
        assert "配当再投資" in text
        assert "console.log" not in text

    def test_returns_none_when_disallowed_by_robots(self):
        with patch("comment.fetcher.is_allowed_by_robots", return_value=False):
            result = fetch_article_text("https://example.com/article/1")
        assert result is None

    def test_returns_none_on_http_error(self):
        import httpx

        with (
            patch("comment.fetcher.is_allowed_by_robots", return_value=True),
            patch("comment.fetcher.httpx.get", side_effect=httpx.ConnectError("timeout")),
        ):
            result = fetch_article_text("https://example.com/article/1")
        assert result is None

    def test_truncates_long_content(self):
        long_html = (
            "<html><body><article>"
            + "".join(f"<p>{'あ' * 100}</p>" for _ in range(50))
            + "</article></body></html>"
        )
        mock_resp = MagicMock()
        mock_resp.text = long_html
        mock_resp.raise_for_status.return_value = None

        with (
            patch("comment.fetcher.is_allowed_by_robots", return_value=True),
            patch("comment.fetcher.httpx.get", return_value=mock_resp),
        ):
            text = fetch_article_text("https://example.com/article/long")

        assert text is not None
        assert len(text) <= 3000
