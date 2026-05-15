"""Firestore の掲載元プロフィール（Markdown）→ 安全な HTML。"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import markdown
import nh3
from shared.config import get_settings

logger = logging.getLogger(__name__)

_INTRO_MD_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "em",
        "b",
        "i",
        "ul",
        "ol",
        "li",
        "h2",
        "h3",
        "h4",
        "a",
        "code",
        "pre",
        "blockquote",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)


def intro_plain_from_feed_doc(data: dict[str, Any]) -> str | None:
    """profile を優先し、空なら旧 investment_style_intro（移行残り）を返す。"""
    for key in ("profile", "investment_style_intro"):
        raw = data.get(key)
        if isinstance(raw, str):
            s = raw.strip()
            if s:
                return s
    return None


def render_blog_intro_md(markdown_source: str) -> str:
    """Firestore の紹介本文（Markdown）をサニタイズ済み HTML フラグメントにする。"""
    html_fragment = markdown.markdown(
        markdown_source,
        extensions=["extra", "nl2br", "sane_lists"],
        output_format="html",
    )
    return nh3.clean(
        html_fragment,
        tags=_INTRO_MD_TAGS,
        attributes={
            "a": {"href", "title"},
            "code": {"class"},
            "th": {"colspan", "rowspan"},
            "td": {"colspan", "rowspan"},
        },
        url_schemes={"http", "https", "mailto"},
    )


@lru_cache(maxsize=8)
def _firestore_read_client(project: str) -> Any:
    """Firestore 読み取り用クライアントをプロジェクト単位で再利用する。"""
    from google.cloud import firestore  # type: ignore[import-untyped]

    return firestore.Client(project=project)


def get_feed_profile(feed_id: str) -> str | None:
    """Firestore feeds コレクションから紹介本文（Markdown）を取得する。
    未設定・空・エラーは None を返す。
    """
    settings = get_settings()
    if not settings.firestore_project:
        return None
    try:
        client = _firestore_read_client(settings.firestore_project)
        coll = settings.firestore_feeds_collection
        doc = client.collection(coll).document(feed_id).get()
        if doc.exists:
            return intro_plain_from_feed_doc(doc.to_dict() or {})
        return None
    except Exception as exc:
        logger.warning(
            "get_feed_profile failed for feed_id=%s: %s",
            feed_id,
            exc,
            exc_info=True,
        )
        return None
