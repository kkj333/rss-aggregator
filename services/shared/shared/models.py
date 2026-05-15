from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Article:
    id: str
    source_title: str
    feed_url: str
    title: str
    url: str
    summary: str
    author: str | None
    published_at: datetime
    collected_at: datetime
    relevance_score: float | None = field(default=None)
    classified_at: datetime | None = field(default=None)
    classifier_version: str | None = field(default=None)
    ai_comment: str | None = field(default=None)
    commented_at: datetime | None = field(default=None)
    commentator_version: str | None = field(default=None)
