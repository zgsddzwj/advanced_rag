"""
优化2 单元测试：SSE 参数配置化
心跳间隔 / 队列等待超时 / 遗弃队列存活时间均由 settings 驱动
"""
import asyncio
import time

import pytest

from app.conf.settings import settings
from app.utils import sse_utils
from app.utils.sse_utils import (
    SSEEvent, create_sse_queue, push_to_session, sse_generator,
    cleanup_stale_queues, _sse_queues, _sse_loops, _sse_create_times,
    _sse_active_consumers,
)


@pytest.fixture(autouse=True)
def _clean_state():
    _sse_queues.clear()
    _sse_loops.clear()
    _sse_create_times.clear()
    _sse_active_consumers.clear()
    yield
    _sse_queues.clear()
    _sse_loops.clear()
    _sse_create_times.clear()
    _sse_active_consumers.clear()


class TestSSEConfig:
    def test_defaults_match_legacy_constants(self, monkeypatch):
        """默认值必须与演进前硬编码一致（屏蔽环境变量后取默认）"""
        for key in ("SSE_HEARTBEAT_INTERVAL_SECONDS", "SSE_QUEUE_WAIT_TIMEOUT_SECONDS", "SSE_QUEUE_MAX_AGE_SECONDS"):
            monkeypatch.delenv(key, raising=False)
        from app.conf.settings import Settings
        s = Settings(_env_file=None)
        assert s.sse_heartbeat_interval_seconds == 15.0
        assert s.sse_queue_wait_timeout_seconds == 10.0
        assert s.sse_queue_max_age_seconds == 600.0

    def test_stale_queue_age_from_settings(self, monkeypatch):
        """遗弃队列的判定时长由配置驱动（缩短后立即清理）"""
        monkeypatch.setattr(settings, "sse_queue_max_age_seconds", 0.05)

        async def _create():
            create_sse_queue("sid-stale")

        asyncio.run(_create())
        assert "sid-stale" in _sse_queues

        time.sleep(0.06)  # 超过配置的存活时间
        cleaned = cleanup_stale_queues()
        assert cleaned == 1
        assert "sid-stale" not in _sse_queues

    def test_active_consumer_survives_cleanup(self, monkeypatch):
        """有活跃消费者的队列即使超龄也不被清理"""
        monkeypatch.setattr(settings, "sse_queue_max_age_seconds", 0.01)

        async def _create():
            create_sse_queue("sid-live")

        asyncio.run(_create())
        _sse_active_consumers.add("sid-live")
        time.sleep(0.03)

        assert cleanup_stale_queues() == 0
        assert "sid-live" in _sse_queues


class TestSSEGeneratorFlow:
    def test_ready_final_flow_and_cleanup(self):
        """正常流：ready → final 后队列清理，事件格式正确"""
        async def _run():
            create_sse_queue("sid-flow")
            push_to_session("sid-flow", SSEEvent.FINAL, {"answer": "done"})

            events = []
            async for chunk in sse_generator("sid-flow", request=None):
                events.append(chunk.strip())
            return events

        events = asyncio.run(_run())
        assert events[0].startswith("event: ready")
        assert any(e.startswith("event: final") and "done" in e for e in events)
        assert "sid-flow" not in _sse_queues  # 流结束后清理

    def test_queue_wait_timeout_message(self, monkeypatch):
        """队列迟迟未创建：按配置超时返回 error 事件，且中文明文（不转义 \\uXXXX）"""
        import json as _json
        monkeypatch.setattr(settings, "sse_queue_wait_timeout_seconds", 0.2)

        async def _run():
            events = []
            async for chunk in sse_generator("sid-missing", request=None):
                events.append(chunk.strip())
            return events

        events = asyncio.run(_run())
        error_events = [e for e in events if e.startswith("event: error")]
        assert error_events, f"未收到 error 事件: {events}"
        data_line = next(l for l in error_events[0].splitlines() if l.startswith("data:"))
        assert "队列创建超时" in data_line  # 原始报文即中文，抓包/日志可读
        assert "队列创建超时" in _json.loads(data_line[len("data:"):])["message"]
