"""
演进6 单元测试：事件驱动强化
事件模型校验、处理器注册表、幂等去重仓储、消费者重试/死信路径
"""
import pytest

from app.events.model import (
    DocumentEvent, EventParseError, build_event, parse_event,
    register_handler, get_handler, registered_types,
    EVENT_ADD, EVENT_UPDATE, EVENT_DELETE,
)
import app.events.handlers  # noqa: F401 — 导入即完成内置处理器注册（消费端契约）
from app.repository.event_dedup_repository import EventDedupRepository
from tests.test_repository import FakeCollection


# ============================================================
#  事件模型
# ============================================================

class TestDocumentEventModel:
    def test_build_event_fills_defaults(self):
        event = build_event(
            event_type=EVENT_ADD, file_title="a.pdf",
            content_hash="h", chunk_count=3, item_name="主题",
        )
        assert len(event.event_id) == 36  # uuid4
        assert event.timestamp is not None
        assert event.metadata["chunk_count"] == 3
        assert event.short_id() == event.event_id[:8]

    def test_parse_valid_event(self):
        raw = build_event(event_type=EVENT_DELETE, file_title="a.pdf").model_dump()
        event = parse_event(raw)
        assert event.event_type == EVENT_DELETE

    def test_parse_missing_required_fields(self):
        with pytest.raises(EventParseError):
            parse_event({"event_type": "DOCUMENT_ADD"})  # 缺 event_id/file_title

    def test_parse_non_dict_payload(self):
        with pytest.raises(EventParseError):
            parse_event("not-a-dict")


# ============================================================
#  处理器注册表
# ============================================================

class TestHandlerRegistry:
    def test_builtin_handlers_registered(self):
        assert get_handler(EVENT_ADD) is not None
        assert get_handler(EVENT_UPDATE) is not None
        assert get_handler(EVENT_DELETE) is not None
        assert get_handler("UNKNOWN_TYPE") is None

    def test_register_and_lookup(self):
        @register_handler("TEST_EVENT_X")
        def handler_x(event):
            return "x"

        assert get_handler("TEST_EVENT_X") is handler_x
        assert "TEST_EVENT_X" in registered_types()

    def test_duplicate_registration_rejected(self):
        @register_handler("TEST_EVENT_DUP")
        def handler_a(event):
            pass

        with pytest.raises(ValueError):
            @register_handler("TEST_EVENT_DUP")
            def handler_b(event):
                pass

    def test_handlers_are_sync(self):
        """处理器必须是同步函数（线程池执行契约）"""
        import inspect
        for t in (EVENT_ADD, EVENT_UPDATE, EVENT_DELETE):
            assert not inspect.iscoroutinefunction(get_handler(t))


# ============================================================
#  幂等去重仓储
# ============================================================

class _FakeDedupCollection(FakeCollection):
    def find_one(self, query):
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None


class TestEventDedupRepository:
    def test_mark_and_check(self):
        repo = EventDedupRepository(_FakeDedupCollection())
        assert repo.is_processed("e1") is False
        repo.mark_processed("e1")
        assert repo.is_processed("e1") is True

    def test_ttl_index_created(self):
        coll = _FakeDedupCollection()
        EventDedupRepository(coll, ttl_days=7)
        # find_one 触发 collection 属性 → 索引创建（expireAfterSeconds 存在）
        assert coll.indexes == []  # 索引通过 create_index 调用注册
        repo = EventDedupRepository(coll, ttl_days=7)
        repo.is_processed("e")
        # FakeCollection.create_index 记录了调用参数
        assert any(idx == "processed_at" for idx in coll.indexes)


# ============================================================
#  消费者：重试 / 死信 / 幂等路径
# ============================================================

class TestConsumerExecution:
    def _make_event(self):
        return build_event(event_type=EVENT_ADD, file_title="doc.pdf")

    def test_retry_then_success(self, monkeypatch):
        """前两次失败第三次成功 → 不抛异常"""
        from app.clients import kafka_consumer as consumer
        monkeypatch.setattr(consumer.settings, "kafka_event_retry_max", 3)
        monkeypatch.setattr(consumer.settings, "kafka_event_retry_delay_seconds", 0)
        monkeypatch.setattr(consumer, "time", _NoSleepTime())

        calls = {"n": 0}

        def flaky(event):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")

        # consumer 通过 `from ... import get_handler` 绑定到自身命名空间
        monkeypatch.setattr(consumer, "get_handler", lambda t: flaky)

        consumer._execute_with_retry(self._make_event())
        assert calls["n"] == 3

    def test_retry_exhausted_raises(self, monkeypatch):
        """重试耗尽 → 抛出异常（由调用方转死信）"""
        from app.clients import kafka_consumer as consumer
        monkeypatch.setattr(consumer.settings, "kafka_event_retry_max", 1)
        monkeypatch.setattr(consumer.settings, "kafka_event_retry_delay_seconds", 0)
        monkeypatch.setattr(consumer, "time", _NoSleepTime())
        monkeypatch.setattr(consumer, "get_handler", lambda t: _always_fail)

        with pytest.raises(RuntimeError):
            consumer._execute_with_retry(self._make_event())

    def test_unknown_event_type_is_noop(self, monkeypatch):
        from app.clients import kafka_consumer as consumer
        monkeypatch.setattr(consumer, "get_handler", lambda t: None)
        consumer._execute_with_retry(self._make_event())  # 不抛异常


def _always_fail(event):
    raise RuntimeError("permanent failure")


class _NoSleepTime:
    """屏蔽消费者模块内的 time.sleep（测试不等待）"""

    def __init__(self):
        self.perf_counter = __import__("time").perf_counter

    def sleep(self, *_):
        pass
