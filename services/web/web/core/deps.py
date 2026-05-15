"""FastAPI Depends と記事ストア。"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Query
from shared.config import get_settings
from shared.storage import ArticleStore, InMemoryArticleStore, create_store


@lru_cache(maxsize=8)
def _article_store_for(
    firestore_project: str,
    firestore_collection: str,
) -> ArticleStore:
    """ストアを設定キーごとにキャッシュ（無引数 lru では初回 get_settings 固定になるのを防ぐ）。"""
    return create_store(
        firestore_project=firestore_project,
        firestore_collection=firestore_collection,
    )


def get_store() -> ArticleStore:
    settings = get_settings()
    if not settings.firestore_project:
        # GOOGLE_CLOUD_PROJECT 未設定（ローカル開発・テスト）はメモリストアで起動を許容する。
        return InMemoryArticleStore()
    return _article_store_for(
        settings.firestore_project,
        settings.firestore_collection,
    )


ArticleStoreDependency = Annotated[ArticleStore, Depends(get_store)]
ArticleLimit = Annotated[int, Query(ge=1, le=200)]

FeedsListPage = Annotated[int, Query(ge=1, le=500)]
