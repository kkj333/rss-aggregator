"""ブラウザ向け HTML ページ。"""

import shared.config
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from shared.config import get_settings

from web.blog.intro import get_feed_profile, render_blog_intro_md
from web.blog.paths import (
    FEED_ID_RE,
    blog_path_segment,
    compute_feed_id,
    resolve_blog_feed,
)
from web.core.constants import (
    ABOUT_META_DESCRIPTION,
    ARTICLE_PAGE_STEP,
    BLOG_DETAIL_ARTICLE_LIMIT,
    FEEDS_LIST_META_DESCRIPTION,
    FEEDS_PAGE_SIZE,
    SITE_META_DESCRIPTION,
)
from web.core.deps import ArticleLimit, ArticleStoreDependency, FeedsListPage
from web.core.resources import templates
from web.syndication.builders import article_list_context, public_origin

router = APIRouter()


@router.get("/blogs", response_class=HTMLResponse)
def blogs_list(request: Request, page: FeedsListPage = 1) -> HTMLResponse:
    settings = get_settings()
    origin = public_origin(settings, request)
    all_feeds = shared.config.load_feeds()
    total = len(all_feeds)
    page_size = FEEDS_PAGE_SIZE
    if total == 0:
        if page != 1:
            raise HTTPException(status_code=404)
        total_pages = 1
        page_feeds: list = []
    else:
        total_pages = (total + page_size - 1) // page_size
        if page > total_pages:
            raise HTTPException(status_code=404)
        start = (page - 1) * page_size
        page_feeds = all_feeds[start : start + page_size]
    canonical = f"{origin}/blogs" if page <= 1 else f"{origin}/blogs?page={page}"
    feeds_with_paths = [(feed, blog_path_segment(feed)) for feed in page_feeds]
    return templates.TemplateResponse(
        request=request,
        name="blogs.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "ga_measurement_id": settings.ga_measurement_id,
            "meta_description": FEEDS_LIST_META_DESCRIPTION,
            "canonical_url": canonical,
            "rss_absolute_url": f"{origin}/rss",
            "feeds_with_paths": feeds_with_paths,
            "page": page,
            "total_pages": total_pages,
            "total_feeds": total,
            "page_size": page_size,
        },
    )


@router.get("/feeds")
def feeds_redirect(request: Request, page: FeedsListPage = 1) -> RedirectResponse:
    """旧 /feeds を /blogs へ 301 リダイレクト。"""
    target = "/blogs" if page == 1 else f"/blogs?page={page}"
    return RedirectResponse(url=target, status_code=301)


@router.get("/blogs/{path_segment}", response_model=None)
def blog_detail(
    request: Request, path_segment: str, article_store: ArticleStoreDependency
) -> RedirectResponse | HTMLResponse:
    all_feeds = shared.config.load_feeds()
    feed_source = resolve_blog_feed(path_segment, all_feeds)
    if feed_source is None:
        raise HTTPException(status_code=404)

    stable_id = compute_feed_id(feed_source.url)
    settings = get_settings()
    origin = public_origin(settings, request)

    if feed_source.slug and FEED_ID_RE.match(path_segment) and path_segment == stable_id:
        return RedirectResponse(url=f"/blogs/{feed_source.slug}", status_code=301)

    intro_raw = get_feed_profile(stable_id)
    intro_html = render_blog_intro_md(intro_raw) if intro_raw else None
    articles = article_store.list_by_feed(feed_source.url, BLOG_DETAIL_ARTICLE_LIMIT)
    canonical_segment = blog_path_segment(feed_source)
    canonical = f"{origin}/blogs/{canonical_segment}"
    meta_description = f"{feed_source.title}の記事一覧。登録フィードの新着記事です。"
    return templates.TemplateResponse(
        request=request,
        name="blog_detail.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "ga_measurement_id": settings.ga_measurement_id,
            "meta_description": meta_description,
            "canonical_url": canonical,
            "rss_absolute_url": f"{origin}/rss",
            "feed": feed_source,
            "intro_html": intro_html,
            "articles": articles,
        },
    )


@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    origin = public_origin(settings, request)
    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "ga_measurement_id": settings.ga_measurement_id,
            "meta_description": ABOUT_META_DESCRIPTION,
            "canonical_url": f"{origin}/about",
            "rss_absolute_url": f"{origin}/rss",
        },
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request, article_store: ArticleStoreDependency) -> HTMLResponse:
    settings = get_settings()
    origin = public_origin(settings, request)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "ga_measurement_id": settings.ga_measurement_id,
            "meta_description": SITE_META_DESCRIPTION,
            "canonical_url": f"{origin}/",
            "rss_absolute_url": f"{origin}/rss",
            "stats": None,
            **article_list_context(
                article_store, ARTICLE_PAGE_STEP, min_score=settings.relevance_threshold
            ),
        },
    )


@router.get("/articles", response_class=HTMLResponse)
def articles_fragment(
    request: Request,
    article_store: ArticleStoreDependency,
    limit: ArticleLimit = 50,
) -> HTMLResponse:
    settings = get_settings()
    resp = templates.TemplateResponse(
        request=request,
        name="_articles.html",
        context={
            "request": request,
            **article_list_context(article_store, limit, min_score=settings.relevance_threshold),
        },
    )
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp
