"""FastAPI アプリ入口（ルート登録のみ。実装は web.routes / web.core / web.blog 等）。"""

from __future__ import annotations

import mimetypes

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from shared.config import get_settings

from web.blog.paths import blog_path_for_feed_url
from web.core.deps import get_store
from web.core.resources import PACKAGE_DIR, templates
from web.routes.discovery import router as discovery_router
from web.routes.pages import router as pages_router

# mimetypes に .css が無い Slim イメージでは text/plain になり、ブラウザが CSS として扱わない。
mimetypes.add_type("text/css", ".css")

templates.env.globals["blog_path_for_feed_url"] = blog_path_for_feed_url

_settings = get_settings()
_openapi_off = (
    {"docs_url": None, "redoc_url": None, "openapi_url": None}
    if not _settings.enable_openapi_docs
    else {}
)
app = FastAPI(title=_settings.app_name, **_openapi_off)
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
app.include_router(pages_router)
app.include_router(discovery_router)

__all__ = ["app", "get_store"]
