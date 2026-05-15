"""掲載元 URL パス（slug / hex）の純粋ロジック。"""

from __future__ import annotations

import pytest
from shared.config import FeedSource

from web.blog.paths import FEED_ID_RE, blog_path_segment, compute_feed_id, resolve_blog_feed

pytestmark = pytest.mark.unit


def test_compute_feed_id_is_64_hex() -> None:
    h = compute_feed_id("https://example.com/feed.xml")
    assert len(h) == 64
    assert FEED_ID_RE.match(h)


def test_blog_path_segment_prefers_slug() -> None:
    f = FeedSource(title="t", url="https://x/f.xml", slug="my-slug")
    assert blog_path_segment(f) == "my-slug"


def test_blog_path_segment_hex_when_no_slug() -> None:
    f = FeedSource(title="t", url="https://x/f.xml")
    assert blog_path_segment(f) == compute_feed_id("https://x/f.xml")


def test_resolve_blog_feed_by_slug() -> None:
    feeds = [FeedSource(title="t", url="https://x/f.xml", slug="s")]
    assert resolve_blog_feed("s", feeds) == feeds[0]


def test_resolve_blog_feed_by_hex() -> None:
    url = "https://x/f.xml"
    feeds = [FeedSource(title="t", url=url)]
    hid = compute_feed_id(url)
    assert resolve_blog_feed(hid, feeds) == feeds[0]
