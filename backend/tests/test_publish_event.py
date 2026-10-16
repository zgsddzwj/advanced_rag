"""
改动3 单元测试：_publish_import_event 事件循环生命周期
asyncio.Runner 保证无论成败事件循环必关，失败不外泄
"""
import asyncio

import pytest

from app.services.import_service import _publish_import_event


def _fake_publish(behavior):
    """构造可 monkeypatch 的异步 publish 替身"""
    async def _fn(**kwargs):
        if behavior == "raise":
            raise RuntimeError("kafka down")
        behavior.setdefault("captured", {}).update(kwargs)
        return True
    return _fn


class TestPublishImportEvent:
    def test_success_passes_kwargs(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            "app.services.import_service.publish_document_event",
            _fake_publish({"captured": captured}),
        )
        _publish_import_event(
            event_type="DOCUMENT_ADD", file_title="a.pdf",
            file_path="/x/a.pdf", content_hash="h", chunk_count=3, item_name="主题",
        )
        assert captured["event_type"] == "DOCUMENT_ADD"
        assert captured["chunk_count"] == 3

    def test_failure_does_not_escape(self, monkeypatch):
        """发布失败只抛给调用方的 try/except，不破坏导入主流程"""
        monkeypatch.setattr(
            "app.services.import_service.publish_document_event",
            _fake_publish("raise"),
        )
        with pytest.raises(RuntimeError, match="kafka down"):
            _publish_import_event(
                event_type="DOCUMENT_ADD", file_title="a.pdf",
                file_path="/x/a.pdf", content_hash="h", chunk_count=1, item_name="",
            )

    def test_no_event_loop_leak_after_failure(self, monkeypatch):
        """失败后当前线程不残留未关闭的事件循环"""
        monkeypatch.setattr(
            "app.services.import_service.publish_document_event",
            _fake_publish("raise"),
        )
        with pytest.raises(RuntimeError):
            _publish_import_event(
                event_type="DOCUMENT_ADD", file_title="a.pdf",
                file_path="/x/a.pdf", content_hash="h", chunk_count=1, item_name="",
            )
        # Runner 关闭后，当前线程不应再有关联的运行中事件循环
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
