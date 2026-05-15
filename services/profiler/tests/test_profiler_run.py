"""run.py のユニットテスト（Firestore・ADK はモック）。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from shared.config import FeedSource


def _make_feeds(*titles_and_urls) -> list[FeedSource]:
    return [
        FeedSource(title=t, url=u, site_url=f"https://{i}.example.com/")
        for i, (t, u) in enumerate(titles_and_urls)
    ]


@patch("profiler_run._get_firestore_client")
@patch("profiler_run.FeedProfiler")
@patch("profiler_run.load_feeds")
@patch("profiler_run.get_settings")
def test_profiler_run_updates_feeds(
    mock_settings, mock_load_feeds, mock_profiler_cls, mock_fs_client, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

    settings = MagicMock()
    settings.firestore_project = "test-project"
    settings.gemini_location = "global"
    settings.profiler_model = "test-model"
    settings.profiler_skip_existing = False
    settings.firestore_feeds_collection = "feeds"
    mock_settings.return_value = settings

    mock_load_feeds.return_value = _make_feeds(("BlogA", "https://a.example/rss"))

    mock_result = MagicMock()
    mock_result.profile = "プロフィール"
    mock_result.investment_style = ["テック"]
    mock_result.sources = ["https://ref.example.com"]
    mock_result.profiled_at = MagicMock()
    mock_result.profiler_version = "test-model"

    mock_profiler_instance = MagicMock()
    mock_profiler_instance.profile.return_value = mock_result
    mock_profiler_cls.return_value = mock_profiler_instance

    mock_client = MagicMock()
    mock_fs_client.return_value = mock_client

    import profiler_run as run
    run.main()

    captured = capsys.readouterr()
    stats = json.loads(captured.out.strip().splitlines()[-1])
    assert stats["feeds_total"] == 1
    assert stats["updated"] == 1
    assert stats["skipped"] == 0
    assert stats["failed"] == 0


@patch("profiler_run._get_firestore_client")
@patch("profiler_run.FeedProfiler")
@patch("profiler_run.load_feeds")
@patch("profiler_run.get_settings")
def test_profiler_run_skips_existing(
    mock_settings, mock_load_feeds, mock_profiler_cls, mock_fs_client, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

    settings = MagicMock()
    settings.firestore_project = "test-project"
    settings.gemini_location = "global"
    settings.profiler_model = "test-model"
    settings.profiler_skip_existing = True
    settings.firestore_feeds_collection = "feeds"
    mock_settings.return_value = settings

    mock_load_feeds.return_value = _make_feeds(("BlogA", "https://a.example/rss"))

    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"profile": "既存プロフィール"}
    mock_client.collection.return_value.document.return_value.get.return_value = mock_doc
    mock_fs_client.return_value = mock_client

    import profiler_run as run
    run.main()

    captured = capsys.readouterr()
    stats = json.loads(captured.out.strip().splitlines()[-1])
    assert stats["skipped"] == 1
    assert stats["updated"] == 0
    mock_profiler_cls.return_value.profile.assert_not_called()


@patch("profiler_run.get_settings")
def test_profiler_run_exits_without_project(mock_settings) -> None:
    settings = MagicMock()
    settings.firestore_project = None
    mock_settings.return_value = settings

    import profiler_run as run
    with pytest.raises(SystemExit) as exc_info:
        run.main()
    assert exc_info.value.code == 1
