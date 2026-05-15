"""load_feeds の feeds.json 検証（slug など）。"""

from __future__ import annotations

import json

import pytest

from shared.config import load_feeds


def test_load_feeds_accepts_optional_slug(tmp_path) -> None:
    p = tmp_path / "feeds.json"
    p.write_text(
        json.dumps(
            [{"title": "A", "url": "https://a.example/f.xml", "slug": "my-blog"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    feeds = load_feeds(p)
    assert len(feeds) == 1
    assert feeds[0].slug == "my-blog"


def test_load_feeds_rejects_duplicate_slug(tmp_path) -> None:
    p = tmp_path / "feeds.json"
    p.write_text(
        json.dumps(
            [
                {"title": "A", "url": "https://a.example/f.xml", "slug": "dup"},
                {"title": "B", "url": "https://b.example/f.xml", "slug": "dup"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate slug"):
        load_feeds(p)


def test_load_feeds_rejects_slug_that_looks_like_legacy_hex(tmp_path) -> None:
    hex64 = "a" * 64
    p = tmp_path / "feeds.json"
    p.write_text(
        json.dumps(
            [{"title": "A", "url": "https://a.example/f.xml", "slug": hex64}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="64-character hex"):
        load_feeds(p)
