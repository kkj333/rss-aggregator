from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# Web のブログ個別 URL /blogs/{slug} 用（64 桁 hex の feed_id と別物）
_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_FEED_ID_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_SLUG_MAX_LEN = 80


def _repo_root() -> Path:
    """モノレポのルート（uv workspace 起点の `pyproject.toml` があるディレクトリ）。"""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        meta = parent / "pyproject.toml"
        if not meta.is_file():
            continue
        text = meta.read_text(encoding="utf-8")
        if "[tool.uv.workspace]" in text and 'name = "rss-aggregator"' in text:
            return parent
    msg = "Could not locate workspace root (rss-aggregator pyproject.toml)"
    raise RuntimeError(msg)


BASE_DIR = _repo_root()


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _validate_optional_site_url(raw: str | None, index: int) -> str | None:
    """feeds.json の site_url: http(s) の絶対 URL のみ許可。未指定・空は None。"""
    if raw is None:
        return None
    if not isinstance(raw, str):
        msg = f"feeds.json[{index}] site_url must be a string when set"
        raise TypeError(msg)
    trimmed = raw.strip()
    if not trimmed:
        return None
    parsed = urlparse(trimmed)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        msg = f"feeds.json[{index}] site_url must be an http(s) URL with a host"
        raise ValueError(msg)
    return trimmed


def _validate_optional_slug(raw: str | None, index: int) -> str | None:
    """feeds.json の slug: 短いパス用。省略時は Web が feed_url の SHA-256 hex を使う。"""
    if raw is None:
        return None
    if not isinstance(raw, str):
        msg = f"feeds.json[{index}] slug must be a string when set"
        raise TypeError(msg)
    slug = raw.strip()
    if not slug:
        return None
    if len(slug) > _SLUG_MAX_LEN:
        msg = f"feeds.json[{index}] slug must be at most {_SLUG_MAX_LEN} characters"
        raise ValueError(msg)
    if _FEED_ID_HEX_RE.match(slug):
        msg = (
            f"feeds.json[{index}] slug must not be a 64-character hex string "
            "(reserved for legacy feed id)"
        )
        raise ValueError(msg)
    if not _SLUG_RE.match(slug):
        msg = (
            f"feeds.json[{index}] slug must be lowercase ASCII letters, digits, "
            "and hyphens only (e.g. my-blog-slug)"
        )
        raise ValueError(msg)
    return slug


@dataclass(frozen=True)
class FeedSource:
    title: str
    url: str  # 購読用 RSS / Atom
    site_url: str | None = None  # 任意: ブラウザで読むサイトトップ
    user_agent: str | None = None
    slug: str | None = None  # 任意: /blogs/{slug}（未設定時は SHA-256 hex）


@dataclass(frozen=True)
class Settings:
    app_name: str
    firestore_project: str | None
    firestore_collection: str
    feeds_path: Path
    public_base_url: str | None
    ga_measurement_id: str | None
    gemini_location: str
    gemini_model: str
    classify_batch_size: int
    relevance_threshold: float
    commentator_model: str
    comment_batch_size: int
    profiler_model: str
    profiler_skip_existing: bool
    firestore_feeds_collection: str
    enable_openapi_docs: bool

    @staticmethod
    def from_env() -> Settings:
        default_feeds = BASE_DIR / "feeds.json"
        return Settings(
            app_name=os.getenv("APP_NAME", "RSS Aggregator"),
            firestore_project=_optional_env("GOOGLE_CLOUD_PROJECT"),
            firestore_collection=os.getenv("FIRESTORE_COLLECTION", "articles"),
            feeds_path=Path(os.getenv("FEEDS_JSON_PATH", str(default_feeds))),
            public_base_url=_optional_env("PUBLIC_BASE_URL"),
            ga_measurement_id=_optional_env("GA_MEASUREMENT_ID"),
            gemini_location=os.getenv("GEMINI_LOCATION", "global"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
            classify_batch_size=int(os.getenv("CLASSIFY_BATCH_SIZE", "100")),
            relevance_threshold=float(os.getenv("RELEVANCE_THRESHOLD", "0.5")),
            commentator_model=os.getenv("COMMENTATOR_MODEL", "gemini-3-flash-preview"),
            comment_batch_size=int(os.getenv("COMMENT_BATCH_SIZE", "50")),
            profiler_model=os.getenv("PROFILER_MODEL", "gemini-3-flash-preview"),
            profiler_skip_existing=os.getenv("PROFILER_SKIP_EXISTING", "true").lower() != "false",
            firestore_feeds_collection=os.getenv("FIRESTORE_FEEDS_COLLECTION", "feeds"),
            enable_openapi_docs=_env_bool("ENABLE_OPENAPI_DOCS", default=False),
        )


def get_settings() -> Settings:
    return Settings.from_env()


def load_feeds(path: Path | None = None) -> list[FeedSource]:
    if path is None:
        path = get_settings().feeds_path
    if not path.exists():
        return []

    raw_feeds = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_feeds, list):
        msg = "feeds.json must be a JSON array"
        raise TypeError(msg)

    feeds: list[FeedSource] = []
    for index, item in enumerate(raw_feeds):
        if not isinstance(item, dict):
            msg = f"feeds.json[{index}] must be an object"
            raise TypeError(msg)
        try:
            title = item["title"]
            url = item["url"]
        except KeyError as exc:
            missing = exc.args[0]
            msg = f"feeds.json[{index}] missing required key {missing!r}"
            raise KeyError(msg) from exc
        if not isinstance(title, str) or not isinstance(url, str):
            msg = f"feeds.json[{index}] title and url must be strings"
            raise TypeError(msg)
        user_agent = item.get("user_agent")
        if user_agent is not None and not isinstance(user_agent, str):
            msg = f"feeds.json[{index}] user_agent must be a string when set"
            raise TypeError(msg)
        site_raw = item.get("site_url")
        if site_raw is not None and not isinstance(site_raw, str):
            msg = f"feeds.json[{index}] site_url must be a string when set"
            raise TypeError(msg)
        site_url = _validate_optional_site_url(site_raw, index)
        slug_raw = item.get("slug")
        if slug_raw is not None and not isinstance(slug_raw, str):
            msg = f"feeds.json[{index}] slug must be a string when set"
            raise TypeError(msg)
        slug = _validate_optional_slug(slug_raw, index)
        feeds.append(
            FeedSource(title=title, url=url, site_url=site_url, user_agent=user_agent, slug=slug),
        )

    seen_slugs: set[str] = set()
    for f in feeds:
        if f.slug is None:
            continue
        if f.slug in seen_slugs:
            msg = f"duplicate slug in feeds.json: {f.slug!r}"
            raise ValueError(msg)
        seen_slugs.add(f.slug)

    return feeds
