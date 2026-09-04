"""
演进4 单元测试：服务层 + 依赖注入
通过构造函数注入仓储替身，验证用例编排逻辑
"""
import asyncio

import pytest

from app.core.exceptions import FileValidationError, NotFoundError
from app.services.import_service import ImportService, _sanitize_filename
from app.services.document_service import DocumentService


class _FakeBackground:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))


class FakeUpload:
    """上传流替身：与 UploadStream 协议结构兼容"""

    def __init__(self, filename: str, chunks: list):
        self.filename = filename
        self._chunks = list(chunks)

    async def read(self, size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def _submit(service, upload, bg):
    return asyncio.run(service.submit_upload(upload, bg))


class TestImportServiceValidation:
    def setup_method(self):
        self.service = ImportService(meta_repo=object())  # 校验阶段不触达仓储
        self.bg = _FakeBackground()

    def test_empty_filename_rejected(self):
        with pytest.raises(FileValidationError):
            _submit(self.service, FakeUpload("", [b"data"]), self.bg)

    def test_unsupported_extension(self):
        with pytest.raises(FileValidationError) as exc:
            _submit(self.service, FakeUpload("doc.docx", [b"data"]), self.bg)
        assert "docx" in exc.value.message

    def test_file_too_large_aborts_and_cleans_partial_file(self, tmp_path, monkeypatch):
        """流式上传超限：中止读取并删除半截文件"""
        from app.services import import_service as mod
        monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "uploads")
        monkeypatch.setattr(mod, "MAX_FILE_SIZE", 10)

        with pytest.raises(FileValidationError) as exc:
            _submit(self.service, FakeUpload("big.pdf", [b"x" * 8, b"y" * 8]), self.bg)
        assert exc.value.code == "FILE_TOO_LARGE"
        assert list((tmp_path / "uploads").iterdir()) == []  # 半截文件已清理

    def test_valid_upload_streams_to_disk(self, tmp_path, monkeypatch):
        # 上传目录定向到临时目录，避免污染项目目录
        from app.services import import_service as mod
        monkeypatch.setattr(mod, "UPLOAD_DIR", tmp_path / "uploads")
        monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "output")

        upload = FakeUpload("报告.pdf", [b"pdf-", b"content"])
        result = _submit(self.service, upload, self.bg)

        assert result["status"] == "processing"
        assert result["filename"] == "报告.pdf"
        assert len(self.bg.tasks) == 1  # 后台导入任务已注册
        saved = list((tmp_path / "uploads").iterdir())[0]
        assert saved.read_bytes() == b"pdf-content"  # 分块按序落盘

    def test_sanitize_filename_blocks_traversal(self):
        assert _sanitize_filename("../../etc/passwd") == "passwd"
        assert _sanitize_filename("..\\win\\evil.pdf") == "evil.pdf"
        assert _sanitize_filename("normal.pdf") == "normal.pdf"
        assert _sanitize_filename("a<b>:c?.pdf") == "a_b__c_.pdf"


class TestDocumentServiceDelete:
    def test_delete_not_found_everywhere(self):
        """元数据与 Milvus 均无此文档 → 404"""

        class FakeMeta:
            def get(self, title):
                return None

        class FakeMilvus:
            def has_chunks(self, title):
                return False

        service = DocumentService(meta_repo=FakeMeta(), milvus_repo=FakeMilvus())
        import asyncio
        with pytest.raises(NotFoundError):
            asyncio.run(service.delete_document("ghost.pdf"))

    def test_delete_publishes_event_when_in_milvus_only(self):
        """元数据缺失但 Milvus 有索引数据 → 允许删除"""

        class FakeMeta:
            def get(self, title):
                return None

        class FakeMilvus:
            def has_chunks(self, title):
                return True

        published = {}

        async def fake_publish(**kwargs):
            published.update(kwargs)
            return True

        from app.services import document_service as mod
        original = mod.publish_document_event
        mod.publish_document_event = fake_publish
        try:
            service = DocumentService(meta_repo=FakeMeta(), milvus_repo=FakeMilvus())
            import asyncio
            result = asyncio.run(service.delete_document("milvus-only.pdf"))
        finally:
            mod.publish_document_event = original

        assert result["status"] == "deleting"
        assert published["event_type"] == "DOCUMENT_DELETE"

    def test_delete_with_meta_skips_milvus_check(self):
        """元数据存在 → 直接发事件，不回查 Milvus"""

        class FakeMeta:
            def get(self, title):
                return {"file_title": title}

        class FakeMilvus:
            def __init__(self):
                self.checked = False

            def has_chunks(self, title):
                self.checked = True
                return False

        fake_milvus = FakeMilvus()
        published = {}

        async def fake_publish(**kwargs):
            published.update(kwargs)
            return True

        from app.services import document_service as mod
        original = mod.publish_document_event
        mod.publish_document_event = fake_publish
        try:
            service = DocumentService(meta_repo=FakeMeta(), milvus_repo=fake_milvus)
            import asyncio
            asyncio.run(service.delete_document("meta-only.pdf"))
        finally:
            mod.publish_document_event = original

        assert fake_milvus.checked is False
        assert published["event_type"] == "DOCUMENT_DELETE"


class TestDependencyProviders:
    def test_singletons_cached(self):
        from app.dependencies import get_import_service, get_query_service, get_document_service
        assert get_import_service() is get_import_service()
        assert get_query_service() is get_query_service()
        assert get_document_service() is get_document_service()
