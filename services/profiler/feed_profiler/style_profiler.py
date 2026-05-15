"""Google ADK を使ったブログプロフィール生成（Pydantic 構造化出力）。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types as genai_types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

VALID_STYLES = {
    "テック", "ビジネス", "ライフスタイル", "ニュース", "趣味", "その他"
}

_APP_NAME = "rss_aggregator_profiler"
_USER_ID = "profiler"

_SYSTEM_INSTRUCTION = """\
あなたはブログ・サイトのプロフィール調査エージェントです。
ブログ名と URL を受け取り、Web 検索で情報を収集して指定された JSON 形式で返してください。

profile に含める項目（情報が取得できたものだけ）:
- 運営者・サイトの概要（経歴・活動内容など）
- 主なテーマ・カテゴリ
- 更新頻度や特徴
- 関連リンク・SNS

ルール:
- 日本語で回答する
- 断定的な投資助言・銘柄推奨は含めない\
"""

_USER_TEMPLATE = """\
以下のブログについて Web 検索で情報を収集し、プロフィールを生成してください。

ブログ名: {title}
URL: {site_url}\
"""


class ProfileResult(BaseModel):
    profile: str = Field(
        description="Markdown 形式の詳細プロフィール。運営者概要・主なテーマ・関連リンクなどを含む。"
    )
    investment_style: list[str] = Field(
        description=(
            "コンテンツカテゴリの分類。"
            "テック / ビジネス / ライフスタイル / ニュース / 趣味 / その他"
            " から該当するものを選択。複数可。"
        )
    )
    sources: list[str] = Field(
        default_factory=list,
        description="参照した URL の一覧。Web 検索結果から抽出。",
    )
    profiled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    profiler_version: str = Field(default="")

    def normalized_styles(self) -> list[str]:
        """VALID_STYLES に含まれるものだけ返す。空なら ['その他']。"""
        valid = [s for s in self.investment_style if s in VALID_STYLES]
        return valid if valid else ["その他"]


class FeedProfiler:
    """Google ADK エージェント（google_search + Pydantic 構造化出力）でブログプロフィールを生成。"""

    def __init__(
        self,
        project: str,
        location: str = "global",
        model: str = "gemini-3-flash-preview",
    ) -> None:
        self.model = model
        self._project = project
        self._location = location

    def profile(self, title: str, site_url: str | None) -> ProfileResult:
        """ブログ名と URL を受け取り、Web 検索でプロフィールを生成して返す。"""
        agent = LlmAgent(
            name="feed_profiler",
            model=self.model,
            instruction=_SYSTEM_INSTRUCTION,
            tools=[google_search],
            # ADK: structured output は output_schema（generate_content_config に書けない）。
            output_schema=ProfileResult,
        )
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name=_APP_NAME,
            session_service=session_service,
        )
        session = asyncio.run(
            session_service.create_session(app_name=_APP_NAME, user_id=_USER_ID)
        )

        prompt = _USER_TEMPLATE.format(title=title, site_url=site_url or "（不明）")
        logger.debug("[profiler] prompt for %s:\n%s", title, prompt)
        message = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])

        response_text = ""
        for event in runner.run(user_id=_USER_ID, session_id=session.id, new_message=message):
            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text or ""
                break

        if not response_text:
            raise RuntimeError(f"ADK returned empty response for feed: {title}")

        logger.debug("[profiler] raw response (%d chars) for %s:", len(response_text), title)
        logger.debug("%s", response_text)
        result = ProfileResult.model_validate_json(response_text)
        result = result.model_copy(update={
            "investment_style": result.normalized_styles(),
            "profiler_version": self.model,
            "profiled_at": datetime.now(UTC),
        })
        logger.debug(
            "[profiler] parsed result for %s: styles=%s sources=%d profile_len=%d",
            title,
            result.investment_style,
            len(result.sources),
            len(result.profile),
        )
        return result
