from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from shared.models import Article
from shared.published_at import sane_published_at

_FIRESTORE_MAX_BATCH_WRITES = 500


def _article_with_sane_published_at(article: Article) -> Article:
    fixed = sane_published_at(article.published_at, article.collected_at)
    if fixed == article.published_at:
        return article
    return replace(article, published_at=fixed)


class ArticleStore(ABC):
    @abstractmethod
    def upsert_many(self, articles: list[Article]) -> int:
        """Insert new articles and return how many were newly stored."""

    @abstractmethod
    def list_latest(self, limit: int = 50, min_score: float | None = None) -> list[Article]:
        """Return articles ordered by newest publication date first.

        min_score: when set, only include articles whose relevance_score >= min_score
        AND ai_comment is not None (i.e. fully processed articles only).
        When min_score is None, all articles are returned without filtering.
        """

    @abstractmethod
    def list_by_feed(self, feed_url: str, limit: int = 50) -> list[Article]:
        """Return articles for a specific feed_url, newest first."""


class FirestoreArticleStore(ArticleStore):
    def __init__(self, project: str | None, collection_name: str) -> None:
        from google.cloud import firestore

        self.client: Any = firestore.Client(project=project)
        self.collection: Any = self.client.collection(collection_name)

    def upsert_many(self, articles: list[Article]) -> int:
        if not articles:
            return 0

        ordered_unique = _unique_articles_first_wins(articles)
        refs = [self.collection.document(a.id) for a in ordered_unique]
        existing_ids: set[str] = set()
        for snapshot in self.client.get_all(refs):
            if snapshot.exists:
                existing_ids.add(snapshot.id)

        inserted = 0
        batch = self.client.batch()
        ops_in_batch = 0
        for article in ordered_unique:
            if article.id in existing_ids:
                continue
            batch.create(self.collection.document(article.id), _article_to_dict(article))
            inserted += 1
            ops_in_batch += 1
            if ops_in_batch >= _FIRESTORE_MAX_BATCH_WRITES:
                batch.commit()
                batch = self.client.batch()
                ops_in_batch = 0

        if ops_in_batch:
            batch.commit()

        return inserted

    def list_latest(self, limit: int = 50, min_score: float | None = None) -> list[Article]:
        # When filtering by score, fetch extra rows and filter in Python to avoid
        # a composite index on (relevance_score, published_at).
        raw_fetch = limit * 4 if min_score is not None else limit
        fetch_n = min(max(raw_fetch * 5, 150), 500)
        query = self.collection.order_by("published_at", direction="DESCENDING").limit(fetch_n)
        articles: list[Article] = []
        for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            data["id"] = snapshot.id
            articles.append(_article_with_sane_published_at(_row_to_article(data)))
        articles.sort(key=lambda a: (a.published_at, a.collected_at), reverse=True)
        if min_score is None:
            return articles[:limit]
        filtered = [
            a
            for a in articles
            if a.relevance_score is not None
            and a.relevance_score >= min_score
            and a.ai_comment is not None
        ]
        return filtered[:limit]

    def list_by_feed(self, feed_url: str, limit: int = 50) -> list[Article]:
        # feed_url 等価 + published_at 降順の複合インデックスが Firestore 側で必要になる場合がある。
        query = (
            self.collection.where(filter=_field_filter("feed_url", "==", feed_url))
            .order_by("published_at", direction="DESCENDING")
            .limit(limit)
        )
        articles: list[Article] = []
        for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            data["id"] = snapshot.id
            articles.append(_article_with_sane_published_at(_row_to_article(data)))
        return articles


class InMemoryArticleStore(ArticleStore):
    """テスト・ローカル開発用のメモリ内ストア。外部接続不要。"""

    def __init__(self) -> None:
        self._articles: dict[str, Article] = {}

    def upsert_many(self, articles: list[Article]) -> int:
        count = 0
        for article in _unique_articles_first_wins(articles):
            if article.id not in self._articles:
                self._articles[article.id] = article
                count += 1
        return count

    def list_latest(self, limit: int = 50, min_score: float | None = None) -> list[Article]:
        articles = list(self._articles.values())
        if min_score is not None:
            articles = [
                a
                for a in articles
                if a.relevance_score is not None
                and a.relevance_score >= min_score
                and a.ai_comment is not None
            ]
        articles.sort(key=lambda a: (a.published_at, a.collected_at), reverse=True)
        return articles[:limit]

    def list_by_feed(self, feed_url: str, limit: int = 50) -> list[Article]:
        articles = [a for a in self._articles.values() if a.feed_url == feed_url]
        articles.sort(key=lambda a: (a.published_at, a.collected_at), reverse=True)
        return articles[:limit]


def create_store(
    firestore_project: str | None,
    firestore_collection: str,
) -> ArticleStore:
    if not firestore_project:
        msg = "GOOGLE_CLOUD_PROJECT must be set to use Firestore storage"
        raise ValueError(msg)
    return FirestoreArticleStore(firestore_project, firestore_collection)


def _article_to_dict(article: Article) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": article.id,
        "source_title": article.source_title,
        "feed_url": article.feed_url,
        "title": article.title,
        "url": article.url,
        "summary": article.summary,
        "author": article.author,
        "published_at": article.published_at,
        "collected_at": article.collected_at,
    }
    # None でも明示的に書き込むことで Firestore 側の == null クエリを有効にする。
    d["relevance_score"] = article.relevance_score
    d["ai_comment"] = article.ai_comment
    if article.classified_at is not None:
        d["classified_at"] = article.classified_at
    if article.classifier_version is not None:
        d["classifier_version"] = article.classifier_version
    if article.commented_at is not None:
        d["commented_at"] = article.commented_at
    if article.commentator_version is not None:
        d["commentator_version"] = article.commentator_version
    return d


def _row_to_article(row: dict[str, Any]) -> Article:
    raw_classified_at = row.get("classified_at")
    return Article(
        id=row["id"],
        source_title=row["source_title"],
        feed_url=row["feed_url"],
        title=row["title"],
        url=row["url"],
        summary=row["summary"],
        author=row.get("author"),
        published_at=_parse_datetime(row["published_at"]),
        collected_at=_parse_datetime(row["collected_at"]),
        relevance_score=row.get("relevance_score"),
        classified_at=_parse_datetime(raw_classified_at) if raw_classified_at else None,
        classifier_version=row.get("classifier_version"),
        ai_comment=row.get("ai_comment"),
        commented_at=_parse_datetime(row["commented_at"]) if row.get("commented_at") else None,
        commentator_version=row.get("commentator_version"),
    )


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _unique_articles_first_wins(articles: list[Article]) -> list[Article]:
    ordered: list[Article] = []
    seen: set[str] = set()
    for article in articles:
        if article.id in seen:
            continue
        seen.add(article.id)
        ordered.append(article)
    return ordered


class ArticleClassifierStore(ABC):
    @abstractmethod
    def list_unclassified(self, limit: int = 100) -> list[Article]:
        """Return articles that do not yet have a relevance_score."""

    @abstractmethod
    def update_classification(
        self,
        article_id: str,
        relevance_score: float,
        classified_at: datetime,
        classifier_version: str,
    ) -> None:
        """Write classification result back to the article document."""


class FirestoreArticleClassifierStore(ArticleClassifierStore):
    def __init__(self, project: str | None, collection_name: str) -> None:
        from google.cloud import firestore

        self.client: Any = firestore.Client(project=project)
        self.collection: Any = self.client.collection(collection_name)

    def list_unclassified(self, limit: int = 100) -> list[Article]:
        # collector の _article_to_dict が relevance_score を常に書くため、
        # 未分類は relevance_score == null で直接 Firestore から取得できる。
        # Firestore 側で limit をかけるので全件スキャン不要。
        query = self.collection.where(filter=_field_filter("relevance_score", "==", None)).limit(
            limit
        )
        articles: list[Article] = []
        for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            data["id"] = snapshot.id
            articles.append(_row_to_article(data))
        return articles

    def update_classification(
        self,
        article_id: str,
        relevance_score: float,
        classified_at: datetime,
        classifier_version: str,
    ) -> None:
        self.collection.document(article_id).update(
            {
                "relevance_score": relevance_score,
                "classified_at": classified_at,
                "classifier_version": classifier_version,
            }
        )


def _field_filter(field: str, op: str, value: Any) -> Any:
    """Build a Firestore FieldFilter, compatible with both old and new SDK."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return FieldFilter(field, op, value)
    except ImportError:
        return (field, op, value)


def create_classifier_store(
    firestore_project: str | None,
    firestore_collection: str,
) -> ArticleClassifierStore:
    return FirestoreArticleClassifierStore(firestore_project, firestore_collection)


class ArticleCommentatorStore(ABC):
    @abstractmethod
    def list_uncommented(self, min_score: float = 0.5, limit: int = 50) -> list[Article]:
        """Return classified articles above min_score that do not yet have an ai_comment."""

    @abstractmethod
    def update_comment(
        self,
        article_id: str,
        ai_comment: str,
        commented_at: datetime,
        commentator_version: str,
    ) -> None:
        """Write AI comment result back to the article document."""


class FirestoreArticleCommentatorStore(ArticleCommentatorStore):
    def __init__(self, project: str | None, collection_name: str) -> None:
        from google.cloud import firestore

        self.client: Any = firestore.Client(project=project)
        self.collection: Any = self.client.collection(collection_name)

    def list_uncommented(self, min_score: float = 0.5, limit: int = 50) -> list[Article]:
        # ai_comment == null AND relevance_score >= min_score の複合クエリで直接取得する。
        # infra/main.tf の google_firestore_index "uncommented_by_score"
        # (ai_comment ASC, relevance_score ASC) が必要。
        # 旧ドキュメント（ai_comment フィールド欠落）はこのクエリにヒットしない（意図的）。
        query = (
            self.collection.where(filter=_field_filter("ai_comment", "==", None))
            .where(filter=_field_filter("relevance_score", ">=", min_score))
            .limit(limit)
        )
        articles: list[Article] = []
        for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            data["id"] = snapshot.id
            articles.append(_row_to_article(data))
        return articles

    def update_comment(
        self,
        article_id: str,
        ai_comment: str,
        commented_at: datetime,
        commentator_version: str,
    ) -> None:
        self.collection.document(article_id).update(
            {
                "ai_comment": ai_comment,
                "commented_at": commented_at,
                "commentator_version": commentator_version,
            }
        )


def create_commentator_store(
    firestore_project: str | None,
    firestore_collection: str,
) -> ArticleCommentatorStore:
    return FirestoreArticleCommentatorStore(firestore_project, firestore_collection)
