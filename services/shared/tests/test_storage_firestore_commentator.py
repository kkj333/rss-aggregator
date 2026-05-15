"""Firestore commentator store の抽出条件テスト。"""

from __future__ import annotations

from datetime import UTC, datetime

from shared.storage import FirestoreArticleCommentatorStore


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class _FakeQuery:
    def __init__(self, snapshots: list[_FakeSnapshot], recorder: dict):
        self._snapshots = snapshots
        self._recorder = recorder

    def where(self, *, filter):
        self._recorder.setdefault("where_filters", []).append(filter)
        return self

    def limit(self, value: int):
        self._recorder["limit"] = value
        return self

    def stream(self):
        return iter(self._snapshots)


class _FakeCollection:
    def __init__(self, snapshots: list[_FakeSnapshot], recorder: dict):
        self._snapshots = snapshots
        self._recorder = recorder

    def where(self, *, filter):
        self._recorder.setdefault("where_filters", []).append(filter)
        return _FakeQuery(self._snapshots, self._recorder)


def _make_classified_doc(
    doc_id: str,
    relevance_score: float | None,
    ai_comment: str | None = None,
) -> _FakeSnapshot:
    data = {
        "source_title": "テストブログ",
        "feed_url": "https://example.com/feed",
        "title": "記事タイトル",
        "url": "https://example.com/article",
        "summary": "本文抜粋",
        "author": None,
        "published_at": datetime(2026, 1, 1, tzinfo=UTC),
        "collected_at": datetime(2026, 1, 2, tzinfo=UTC),
        "relevance_score": relevance_score,
        "classified_at": datetime(2026, 1, 3, tzinfo=UTC),
        "ai_comment": ai_comment,
    }
    return _FakeSnapshot(doc_id, data)


def test_list_uncommented_uses_compound_firestore_query():
    """ai_comment == null AND relevance_score >= min_score の複合クエリを使うことを確認。"""
    recorder: dict = {}
    # Firestore 側で ai_comment==null かつ relevance_score>=0.5 をフィルタ済みの想定
    snapshots = [
        _make_classified_doc("a1", relevance_score=0.8),   # 未コメント・高スコア → 対象
        _make_classified_doc("a2", relevance_score=0.6),   # 未コメント・高スコア → 対象
    ]

    store = object.__new__(FirestoreArticleCommentatorStore)
    store.collection = _FakeCollection(snapshots, recorder)

    results = store.list_uncommented(min_score=0.5, limit=10)

    assert [a.id for a in results] == ["a1", "a2"]
    # Firestore 側で limit をかけること
    assert recorder["limit"] == 10
    # 2つの where フィルタが発行されること（ai_comment==null, relevance_score>=min_score）
    assert len(recorder["where_filters"]) == 2


def test_list_uncommented_respects_limit():
    """Firestore 側の limit で件数が絞られることを確認。"""
    recorder: dict = {}
    snapshots = [_make_classified_doc(f"a{i}", relevance_score=0.8) for i in range(5)]

    store = object.__new__(FirestoreArticleCommentatorStore)
    store.collection = _FakeCollection(snapshots, recorder)

    store.list_uncommented(min_score=0.5, limit=3)

    # Firestore 側 limit=3 がかかるので、フェイクは全件返すが limit が記録されること
    assert recorder["limit"] == 3


def test_list_uncommented_issues_compound_firestore_query_with_limit():
    """ai_comment==null AND relevance_score>=min_score の複合クエリと limit が発行されることを確認。
    実際の除外は Firestore 側クエリに委ねているため、ここではクエリ構造のみ検証する。"""
    recorder: dict = {}
    snapshots = [
        _make_classified_doc("a1", relevance_score=0.8, ai_comment=None),
        # a2 は Firestore の ai_comment==null クエリで除外される想定（フェイクでは全件来る）
        _make_classified_doc("a2", relevance_score=0.8, ai_comment="コメント済"),
    ]

    store = object.__new__(FirestoreArticleCommentatorStore)
    store.collection = _FakeCollection(snapshots, recorder)

    store.list_uncommented(min_score=0.5, limit=10)

    assert recorder["limit"] == 10
    assert len(recorder["where_filters"]) == 2
