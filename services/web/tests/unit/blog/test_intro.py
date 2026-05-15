"""掲載元紹介文の純粋ロジック（Firestore なし）。"""

from __future__ import annotations

import pytest

from web.blog.intro import intro_plain_from_feed_doc, render_blog_intro_md

pytestmark = pytest.mark.unit


def test_intro_plain_prefers_profile_over_legacy_field() -> None:
    assert (
        intro_plain_from_feed_doc(
            {
                "profile": "new body",
                "investment_style_intro": "old body",
            }
        )
        == "new body"
    )


def test_intro_plain_falls_back_when_profile_empty_or_whitespace() -> None:
    assert (
        intro_plain_from_feed_doc(
            {
                "profile": "   ",
                "investment_style_intro": "legacy intro",
            }
        )
        == "legacy intro"
    )


def test_intro_plain_legacy_only() -> None:
    assert intro_plain_from_feed_doc({"investment_style_intro": "solo"}) == "solo"


def test_intro_plain_returns_none_when_no_usable_strings() -> None:
    assert intro_plain_from_feed_doc({}) is None
    assert (
        intro_plain_from_feed_doc({"profile": "", "investment_style_intro": ""}) is None
    )


def test_intro_plain_skips_non_string_profile_and_uses_legacy() -> None:
    assert (
        intro_plain_from_feed_doc(
            {"profile": None, "investment_style_intro": "from legacy"}
        )
        == "from legacy"
    )


def test_render_blog_intro_md_emits_strong_for_bold() -> None:
    out = render_blog_intro_md("Hello **world**")
    assert "<strong>world</strong>" in out


def test_render_blog_intro_md_strips_raw_script_tags() -> None:
    out = render_blog_intro_md("<script>alert(1)</script>plain")
    assert "<script>" not in out
    assert "plain" in out


def test_render_blog_intro_md_strips_javascript_links() -> None:
    out = render_blog_intro_md("[x](javascript:alert(1))")
    assert "javascript:" not in out
