"""
改动3 单元测试：/query/ask 请求校验
- query 必填且限长（既有行为守护）
- session_id trim + 64 字符上限（新校验）
"""
import pytest
from pydantic import ValidationError

from app.query_process.api.query_service import QueryRequest


class TestQueryRequestValidation:
    def test_query_required(self):
        with pytest.raises(ValidationError):
            QueryRequest(query="   ")
        with pytest.raises(ValidationError):
            QueryRequest(query="x" * 2001)

    def test_query_trimmed(self):
        req = QueryRequest(query="  设备参数  ")
        assert req.query == "设备参数"

    def test_session_id_empty_allowed(self):
        """空 session_id 合法（服务端自动生成）"""
        assert QueryRequest(query="hi").session_id == ""

    def test_session_id_trimmed(self):
        req = QueryRequest(query="hi", session_id="  abc123  ")
        assert req.session_id == "abc123"

    def test_session_id_too_long_rejected(self):
        with pytest.raises(ValidationError) as exc:
            QueryRequest(query="hi", session_id="s" * 65)
        assert "session_id" in str(exc.value)

    def test_session_id_64_chars_accepted(self):
        req = QueryRequest(query="hi", session_id="s" * 64)
        assert len(req.session_id) == 64
