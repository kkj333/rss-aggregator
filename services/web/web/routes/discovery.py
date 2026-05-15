"""JSON API・RSS・robots / sitemap・ヘルス・favicon（ページ HTML 以外）。"""

import shared.config
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from shared.config import get_settings

from web.blog.paths import blog_path_segment
from web.core.deps import ArticleLimit, ArticleStoreDependency
from web.core.resources import FAVICON_PNG
from web.syndication.builders import build_rss_xml, public_origin, sitemap_urlset_xml

router = APIRouter()


@router.get("/favicon.ico")
def favicon_ico() -> FileResponse:
    """GET /favicon.ico: return PNG (some clients reject SVG at this path)."""
    return FileResponse(FAVICON_PNG, media_type="image/png")


@router.get("/api/feeds")
def api_feeds() -> list[dict[str, str | None]]:
    """実行時に読み込んでいる feeds.json の内容（件数・URLの切り分け用）。"""
    return [
        {
            "title": f.title,
            "url": f.url,
            "site_url": f.site_url,
            "slug": f.slug,
        }
        for f in shared.config.load_feeds()
    ]


@router.get("/api/articles")
def api_articles(
    article_store: ArticleStoreDependency,
    limit: ArticleLimit = 50,
) -> list[dict[str, str | None]]:
    return [
        {
            "id": article.id,
            "source_title": article.source_title,
            "title": article.title,
            "url": article.url,
            "summary": article.summary,
            "author": article.author,
            "published_at": article.published_at.isoformat(),
            "collected_at": article.collected_at.isoformat(),
        }
        for article in article_store.list_latest(limit=limit)
    ]


@router.get("/rss")
def rss_feed(
    request: Request,
    article_store: ArticleStoreDependency,
    limit: ArticleLimit = 50,
) -> Response:
    """集約した新着を RSS 2.0 で返す（各 item の link は元記事 URL）。"""
    settings = get_settings()
    base = public_origin(settings, request)
    # RSS の「サイト側ホーム」として掲載元一覧ページを指す（購読アプリがフィード情報から開く URL）
    channel_site_url = f"{base}/blogs"
    feed_self_url = f"{base}/rss"
    description = (
        "複数の RSS/Atom フィードから集めた新着です。各記事のリンクは元サイトの記事へ飛びます。"
    )
    xml = build_rss_xml(
        channel_title=settings.app_name,
        channel_link=channel_site_url,
        channel_description=description,
        feed_self_url=feed_self_url,
        articles=article_store.list_latest(limit=limit, min_score=settings.relevance_threshold),
    )
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/rss+xml; charset=utf-8",
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(request: Request) -> PlainTextResponse:
    settings = get_settings()
    origin = public_origin(settings, request)
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "",
            "Disallow: /api/",
            "",
            f"Sitemap: {origin}/sitemap.xml",
            "",
        ],
    )
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml")
def sitemap_xml(request: Request) -> Response:
    settings = get_settings()
    origin = public_origin(settings, request)
    feeds = shared.config.load_feeds()
    blog_urls = [f"{origin}/blogs/{blog_path_segment(f)}" for f in feeds]
    urls = [f"{origin}/", f"{origin}/about", f"{origin}/blogs", *blog_urls]
    xml = sitemap_urlset_xml(urls=urls)
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/xml; charset=utf-8",
    )


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
