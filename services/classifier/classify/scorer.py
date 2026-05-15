"""Gemini（Vertex AI）を使った記事関連度スコアリング。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = """\
あなたはブログ記事の関連度を判定するアシスタントです。
以下の基準で記事が「登録フィードのテーマに合っているか」を 0.0〜1.0 のスコアで評価してください。

高スコア（0.7〜1.0）:
- フィードの主題に沿った具体的な知見・実践・分析
- 読者に有益な情報がまとまっている

低スコア（0.0〜0.3）:
- 主題と無関係な話題
- 宣伝・広告が中心のコンテンツ
- 内容が薄い近況報告のみ

JSON のみ返答し、他のテキストは一切含めないこと。
"""

_USER_TEMPLATE = """\
タイトル: {title}
本文抜粋: {summary}
"""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance_score": {
            "type": "number",
            "description": "0.0〜1.0 の関連度スコア（フィードテーマとの一致度）",
        },
        "reason": {
            "type": "string",
            "description": "スコアの根拠（30文字以内）",
        },
    },
    "required": ["relevance_score", "reason"],
}


@dataclass(frozen=True)
class ScoreResult:
    relevance_score: float
    reason: str
    classified_at: datetime
    classifier_version: str


class ArticleScorer:
    def __init__(
        self,
        project: str,
        location: str = "global",
        model: str = "gemini-3-flash-preview",
    ) -> None:
        self.client = genai.Client(vertexai=True, project=project, location=location)
        self.model = model

    def score(self, title: str, summary: str) -> ScoreResult:
        prompt = _USER_TEMPLATE.format(title=title, summary=summary[:400])
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.0,
            ),
        )
        data = json.loads(response.text)
        raw_score = float(data["relevance_score"])
        relevance_score = max(0.0, min(1.0, raw_score))
        return ScoreResult(
            relevance_score=relevance_score,
            reason=str(data.get("reason", "")),
            classified_at=datetime.now(UTC),
            classifier_version=self.model,
        )
