"""Gemini（Vertex AI）を使った記事 AI コメント生成。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from google import genai
from google.genai import types

from comment.fetcher import fetch_article_text

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = """\
あなたはブログ記事に一言コメントを添えるアシスタントです。
記事のタイトル・本文抜粋・（取得できた場合は）本文全文を受け取り、
読者の視点から記事の要点や注目ポイントを一文（30〜60文字程度）で端的にコメントしてください。

ルール:
- 日本語で回答する
- コメントのみ返す（前置き・説明文は不要）
- タイトルの言い換えは禁止。本文にある具体的な数字・結論・驚きを1つ含めること
- 断定的な助言や勧誘表現は避ける
- 本文全文が提供されている場合はそちらを優先して使う
"""

_USER_TEMPLATE_WITH_BODY = """\
タイトル: {title}
本文抜粋: {summary}
本文全文:
{body}"""

_USER_TEMPLATE_SUMMARY_ONLY = """\
タイトル: {title}
本文抜粋: {summary}"""


@dataclass(frozen=True)
class CommentResult:
    ai_comment: str
    commented_at: datetime
    commentator_version: str
    prompt_tokens: int = 0
    candidates_tokens: int = 0
    total_tokens: int = 0


class ArticleCommenter:
    def __init__(
        self,
        project: str,
        location: str = "global",
        model: str = "gemini-3-flash-preview",
    ) -> None:
        self.model = model
        self.client = genai.Client(vertexai=True, project=project, location=location)

    def comment(self, title: str, summary: str, url: str | None = None) -> CommentResult:
        """記事タイトル・本文抜粋・URL から一言コメントを生成して返す。

        url が指定された場合は robots.txt を確認したうえで本文を取得し、
        プロンプトに含める。取得できない場合は summary のみで生成する。
        """
        body: str | None = None
        if url:
            body = fetch_article_text(url)
            if body:
                logger.debug("Fetched article body (%d chars): %s", len(body), url)
            else:
                logger.debug("Could not fetch article body, using summary only: %s", url)

        if body:
            prompt = _USER_TEMPLATE_WITH_BODY.format(
                title=title, summary=summary[:400], body=body
            )
        else:
            prompt = _USER_TEMPLATE_SUMMARY_ONLY.format(title=title, summary=summary[:400])

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
            ),
        )
        reply_text = (response.text or "").strip()

        if not reply_text:
            raise RuntimeError(f"Gemini returned empty response for article: {title[:60]}")

        usage = response.usage_metadata
        prompt_tokens = (usage.prompt_token_count or 0) if usage else 0
        candidates_tokens = (usage.candidates_token_count or 0) if usage else 0
        total_tokens = (usage.total_token_count or 0) if usage else 0

        logger.info(
            "tokens: prompt=%d candidates=%d total=%d | %s",
            prompt_tokens,
            candidates_tokens,
            total_tokens,
            title[:60],
        )

        return CommentResult(
            ai_comment=reply_text,
            commented_at=datetime.now(UTC),
            commentator_version=self.model,
            prompt_tokens=prompt_tokens,
            candidates_tokens=candidates_tokens,
            total_tokens=total_tokens,
        )
