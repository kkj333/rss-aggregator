"""Firestore classifier store の抽出条件テスト。"""

from __future__ import annotations

from datetime import UTC, datetime

from shared.storage import FirestoreArticleClassifierStore


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

    def order_by(self, field: str, direction: str):
        self._recorder["order_by"] = (field, direction)
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
        self._recorder["where"] = filter
        return _FakeQuery(self._snapshots, self._recorder)


def _make_base_doc() -> dict:
    return {
        "source_title": "テストブログ",
        "feed_url": "https://example.com/feed",
        "title": "記事タイトル",
        "url": "https://example.com/article",
        "summary": "本文抜粋",
        "author": None,
        "published_at": datetime(2026, 1, 1, tzinfo=UTC),
        "collected_at": datetime(2026, 1, 2, tzinfo=UTC),
    }


def test_list_unclassified_uses_direct_firestore_query():
    recorder: dict = {}
    base = _make_base_doc()
    # Firestore 側で relevance_score == null をフィルタ済みの想定でスナップショットを渡す
    snapshots = [
        _FakeSnapshot("a1", {**base}),  # relevance_score 欠落（旧ドキュメント）
        _FakeSnapshot("a2", {**base, "relevance_score": None}),  # 未分類
    ]

    store = object.__new__(FirestoreArticleClassifierStore)
    store.collection = _FakeCollection(snapshots, recorder)

    results = store.list_unclassified(limit=10)

    assert [a.id for a in results] == ["a1", "a2"]
    # relevance_score == null で直接 Firestore クエリ、Firestore 側で limit をかける。
    assert recorder["limit"] == 10
