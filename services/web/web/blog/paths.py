"""ブログ一覧・詳細の URL パス（slug / legacy hex）。"""

from __future__ import annotations

import hashlib
import re

import shared.config
from shared.config import FeedSource

FEED_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def compute_feed_id(feed_url: str) -> str:
    """feed_url の SHA-256 hex（64 文字）を返す。"""
    return hashlib.sha256(feed_url.encode("utf-8")).hexdigest()


def blog_path_segment(feed: FeedSource) -> str:
    """一覧・canonical 用のパス片。slug があればそれ、なければ hex feed_id。"""
    if feed.slug:
        return feed.slug
    return compute_feed_id(feed.url)


def blog_path_for_feed_url(feed_url: str) -> str:
    """記事の feed_url から /blogs/{segment} の segment を返す（一覧の掲載元リンク用）。"""
    for f in shared.config.load_feeds():
        if f.url == feed_url:
            return blog_path_segment(f)
    return compute_feed_id(feed_url)


def resolve_blog_feed(path_segment: str, feeds: list[FeedSource]) -> FeedSource | None:
    """パスが legacy の 64 hex か slug かでフィードを引く。"""
    if FEED_ID_RE.match(path_segment):
        return next((f for f in feeds if compute_feed_id(f.url) == path_segment), None)
    return next((f for f in feeds if f.slug == path_segment), None)
