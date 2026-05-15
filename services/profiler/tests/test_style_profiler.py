"""FeedProfiler のユニットテスト（ADK・Firestore はモック）。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from feed_profiler.style_profiler import VALID_STYLES, FeedProfiler, ProfileResult

# ── ProfileResult バリデーション ───────────────────────────────────────────────

def test_profile_result_parse_valid() -> None:
    data = {
        "profile": "テスト",
        "investment_style": ["テック"],
        "sources": ["https://example.com"],
    }
    result = ProfileResult.model_validate(data)
    assert result.profile == "テスト"
    assert result.investment_style == ["テック"]
    assert result.sources == ["https://example.com"]


def test_profile_result_sources_defaults_to_empty() -> None:
    result = ProfileResult.model_validate({"profile": "x", "investment_style": ["ビジネス"]})
    assert result.sources == []


def test_profile_result_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        ProfileResult.model_validate({"investment_style": ["テック"]})


# ── normalized_styles ──────────────────────────────────────────────────────────

def test_normalized_styles_filters_invalid() -> None:
    r = ProfileResult(profile="x", investment_style=["テック", "無効"])
    assert r.normalized_styles() == ["テック"]


def test_normalized_styles_empty_falls_back_to_other() -> None:
    r = ProfileResult(profile="x", investment_style=[])
    assert r.normalized_styles() == ["その他"]


def test_normalized_styles_all_invalid_falls_back() -> None:
    r = ProfileResult(profile="x", investment_style=["unknown"])
    assert r.normalized_styles() == ["その他"]


def test_all_valid_styles_accepted() -> None:
    r = ProfileResult(profile="x", investment_style=list(VALID_STYLES))
    assert set(r.normalized_styles()) == VALID_STYLES


# ── FeedProfiler.profile（ADK Runner をモック） ────────────────────────────────

def _make_mock_runner(response_json: str):
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content.parts = [MagicMock(text=response_json)]

    mock_session = MagicMock()
    mock_session.id = "sess-1"
    mock_session_service = MagicMock()
    mock_session_service.create_session = AsyncMock(return_value=mock_session)

    mock_runner = MagicMock()
    mock_runner.run.return_value = iter([mock_event])

    return mock_runner, mock_session_service


@patch("feed_profiler.style_profiler.Runner")
@patch("feed_profiler.style_profiler.InMemorySessionService")
@patch("feed_profiler.style_profiler.LlmAgent")
def test_profiler_returns_profile_result(mock_agent_cls, mock_session_cls, mock_runner_cls) -> None:
    response = json.dumps({
        "profile": "サンプルブログの紹介",
        "investment_style": ["テック"],
        "sources": ["https://example.com"],
    })
    mock_runner, mock_session_service = _make_mock_runner(response)
    mock_session_cls.return_value = mock_session_service
    mock_runner_cls.return_value = mock_runner

    profiler = FeedProfiler(project="test-project", model="test-model")
    result = profiler.profile(title="サンプルブログ", site_url="https://example.com/")

    assert mock_agent_cls.call_args.kwargs.get("output_schema") is ProfileResult

    assert isinstance(result, ProfileResult)
    assert result.profile == "サンプルブログの紹介"
    assert result.investment_style == ["テック"]
    assert result.sources == ["https://example.com"]
    assert result.profiler_version == "test-model"


@patch("feed_profiler.style_profiler.Runner")
@patch("feed_profiler.style_profiler.InMemorySessionService")
@patch("feed_profiler.style_profiler.LlmAgent")
def test_profiler_raises_on_empty_response(
    mock_agent_cls, mock_session_cls, mock_runner_cls
) -> None:
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = False

    mock_session = MagicMock()
    mock_session.id = "sess-1"
    mock_session_service = MagicMock()
    mock_session_service.create_session = AsyncMock(return_value=mock_session)
    mock_session_cls.return_value = mock_session_service

    mock_runner = MagicMock()
    mock_runner.run.return_value = iter([mock_event])
    mock_runner_cls.return_value = mock_runner

    profiler = FeedProfiler(project="test-project")
    with pytest.raises(RuntimeError, match="empty response"):
        profiler.profile(title="テスト", site_url=None)


@patch("feed_profiler.style_profiler.Runner")
@patch("feed_profiler.style_profiler.InMemorySessionService")
@patch("feed_profiler.style_profiler.LlmAgent")
def test_profiler_raises_on_invalid_json(
    mock_agent_cls, mock_session_cls, mock_runner_cls
) -> None:
    mock_runner, mock_session_service = _make_mock_runner("invalid json")
    mock_session_cls.return_value = mock_session_service
    mock_runner_cls.return_value = mock_runner

    profiler = FeedProfiler(project="test-project")
    with pytest.raises(ValidationError):
        profiler.profile(title="テスト", site_url=None)
