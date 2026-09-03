"""
演进3 单元测试：Repository 数据访问层
用内存替身验证仓储行为，不依赖 MongoDB / Milvus
"""
import pytest

from app.repository.chat_history_repository import ChatHistoryRepository
from app.repository.document_meta_repository import DocumentMetaRepository


class FakeCollection:
    """pymongo Collection 的最小内存替身"""

    def __init__(self):
        self.docs = {}  # _id -> doc
        self._next_id = 0
        self.indexes = []
        self.upsert_calls = 0

    def create_index(self, spec):
        self.indexes.append(spec)
        return "idx"

    def insert_one(self, document):
        self._next_id += 1
        _id = f"id{self._next_id}"
        doc = dict(document)
        doc["_id"] = _id
        self.docs[_id] = doc

        class R:
            inserted_id = _id
        return R()

    def find_one(self, query):
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    def find(self, query, projection=None):
        docs = [
            dict(d) for d in self.docs.values()
            if all(d.get(k) == v for k, v in query.items())
        ]
        if projection and projection.get("_id") == 0:
            for d in docs:
                d.pop("_id", None)
        return FakeCursor(docs)

    def update_one(self, query, update, upsert=False):
        self.upsert_calls += 1
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update["$set"])
                return
        if upsert:
            new_doc = dict(query)
            new_doc.update(update["$set"])
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            self._next_id += 1
            new_doc["_id"] = f"id{self._next_id}"
            self.docs[new_doc["_id"]] = new_doc

    def delete_many(self, query):
        matched = [
            _id for _id, doc in self.docs.items()
            if all(doc.get(k) == v for k, v in query.items())
        ]
        for _id in matched:
            self.docs.pop(_id)

        class R:
            deleted_count = len(matched)
        return R()

    def delete_one(self, query):
        for _id, doc in self.docs.items():
            if all(doc.get(k) == v for k, v in query.items()):
                self.docs.pop(_id)

                class R:
                    deleted_count = 1
                return R()

        class R:
            deleted_count = 0
        return R()

    def count_documents(self, query):
        return sum(
            1 for doc in self.docs.values()
            if all(doc.get(k) == v for k, v in query.items())
        )


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction):
        self._docs.sort(key=lambda d: d.get(field, 0), reverse=(direction == -1))
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __list__(self):
        return self._docs

    def to_list(self):
        return self._docs

    def __len__(self):
        return len(self._docs)


def _as_list(cursor):
    """兼容 pymongo cursor 的 list() 语义"""
    try:
        return list(cursor)
    except TypeError:
        return cursor.to_list()


@pytest.fixture
def fake_coll():
    return FakeCollection()


class TestChatHistoryRepository:
    def test_save_and_get_recent(self, fake_coll):
        repo = ChatHistoryRepository(fake_coll)
        repo.save_message("s1", "user", "你好", rewritten_query="您好")
        repo.save_message("s1", "assistant", "你好！有什么可以帮你？")

        messages = repo.get_recent("s1")
        assert len(messages) == 2
        roles = {m["role"] for m in messages}
        assert roles == {"user", "assistant"}
        by_role = {m["role"]: m for m in messages}
        assert by_role["user"]["text"] == "你好"
        assert by_role["user"]["rewritten_query"] == "您好"
        assert by_role["assistant"]["text"] == "你好！有什么可以帮你？"
        assert isinstance(messages[0]["_id"], str)

    def test_session_isolation(self, fake_coll):
        repo = ChatHistoryRepository(fake_coll)
        repo.save_message("s1", "user", "a")
        repo.save_message("s2", "user", "b")
        assert repo.count("s1") == 1
        assert repo.count("s2") == 1

    def test_clear(self, fake_coll):
        repo = ChatHistoryRepository(fake_coll)
        repo.save_message("s1", "user", "a")
        deleted = repo.clear("s1")
        assert deleted == 1
        assert repo.count("s1") == 0

    def test_get_recent_ordering_and_limit(self, fake_coll):
        """最近 N 条按时间正序返回"""
        repo = ChatHistoryRepository(fake_coll, )
        import time
        for i in range(5):
            fake_coll.insert_one({"session_id": "s", "ts": time.time() + i, "role": "user", "text": str(i)})
        messages = repo.get_recent("s", limit=3)
        assert [m["text"] for m in messages] == ["2", "3", "4"]


class TestDocumentMetaRepository:
    def test_upsert_returns_old_doc(self, fake_coll):
        repo = DocumentMetaRepository(fake_coll)
        first = repo.upsert("doc1.pdf", content_hash="h1", chunk_count=3)
        assert first == {}  # 首次无旧记录

        second = repo.upsert("doc1.pdf", content_hash="h2", chunk_count=5)
        assert second["content_hash"] == "h1"  # 返回旧记录供 ADD/UPDATE 判定

        current = repo.get("doc1.pdf")
        assert current["content_hash"] == "h2"

    def test_mark_status(self, fake_coll):
        repo = DocumentMetaRepository(fake_coll)
        repo.upsert("doc.pdf", content_hash="h")
        repo.mark_status("doc.pdf", "syncing")
        assert repo.get("doc.pdf")["status"] == "syncing"

    def test_delete(self, fake_coll):
        repo = DocumentMetaRepository(fake_coll)
        repo.upsert("doc.pdf", content_hash="h")
        assert repo.delete("doc.pdf") is True
        assert repo.delete("doc.pdf") is False  # 二次删除
        assert repo.get("doc.pdf") is None

    def test_list_all_excludes_id(self, fake_coll):
        repo = DocumentMetaRepository(fake_coll)
        repo.upsert("a.pdf", content_hash="h1")
        repo.upsert("b.pdf", content_hash="h2")
        docs = repo.list_all()
        assert len(docs) == 2
        assert all("_id" not in d for d in docs)
