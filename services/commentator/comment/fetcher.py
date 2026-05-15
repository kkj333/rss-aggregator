"""記事URLからテキストを取得するフェッチャー。

robots.txt を確認し許可されている場合のみ本文を取得する。
"""

from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENT = "rss-aggregator-commentator/1.0"
_FETCH_TIMEOUT = 10.0
_MAX_CONTENT_CHARS = 3000


def is_allowed_by_robots(url: str) -> bool:
    """robots.txt を確認し、指定 URL へのアクセスが許可されているか返す。"""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        # robots.txt が取得できない場合は許可とみなす
        logger.debug("Could not fetch robots.txt for %s, assuming allowed", parsed.netloc)
        return True
    return rp.can_fetch(_USER_AGENT, url)


def fetch_article_text(url: str) -> str | None:
    """記事URLから本文テキストを取得して返す。

    robots.txt で禁止されている場合、または取得に失敗した場合は None を返す。
    """
    if not is_allowed_by_robots(url):
        logger.info("robots.txt disallows fetching: %s", url)
        return None

    try:
        response = httpx.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
    except Exception:
        logger.warning("Failed to fetch article URL: %s", url)
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # <script> <style> を除去
    for tag in soup(["script", "style"]):
        tag.decompose()

    # <article> > <main> > <body> の順で本文コンテナを探す
    container = soup.find("article") or soup.find("main") or soup.find("body")
    if container is None:
        return None

    paragraphs = [p.get_text(separator=" ", strip=True) for p in container.find_all("p")]
    text = "\n".join(p for p in paragraphs if p)
    return text[:_MAX_CONTENT_CHARS] if text else None
