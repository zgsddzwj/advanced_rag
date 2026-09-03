"""
演进2 单元测试：统一响应信封 + 全局异常处理
用最小 FastAPI 应用验证各异常类型 → 信封转换，不依赖任何基础设施
"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

from app.core.error_handlers import register_error_handlers
from app.core.exceptions import (
    AppError,
    BadRequestError,
    FileValidationError,
    NotFoundError,
    UpstreamServiceError,
)
from app.core.response import fail, ok


def build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    class Body(BaseModel):
        text: str

        @field_validator("text")
        @classmethod
        def no_empty(cls, v: str) -> str:
            if not v.strip():
                raise ValueError("text 不能为空")
            return v

    @app.get("/ok")
    async def endpoint_ok():
        return ok({"answer": 42})

    @app.get("/bad-request")
    async def endpoint_bad():
        raise BadRequestError("参数有误")

    @app.get("/not-found")
    async def endpoint_nf():
        raise NotFoundError("文档不存在: demo.pdf")

    @app.get("/file-too-large")
    async def endpoint_file():
        raise FileValidationError("文件大小超过限制", code="FILE_TOO_LARGE")

    @app.get("/upstream")
    async def endpoint_upstream():
        raise UpstreamServiceError("Milvus 不可用", upstream="milvus")

    @app.get("/http-exc")
    async def endpoint_http():
        raise HTTPException(status_code=401, detail="未授权")

    @app.get("/boom")
    async def endpoint_boom():
        raise RuntimeError("数据库密码是 123456")

    @app.post("/validate")
    async def endpoint_validate(body: Body):
        return ok(body.model_dump())

    return app


@pytest.fixture(scope="module")
def client():
    return TestClient(build_app(), raise_server_exceptions=False)


class TestSuccessEnvelope:
    def test_ok_envelope(self, client):
        resp = client.get("/ok")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"code": "OK", "message": "ok", "data": {"answer": 42}}


class TestAppErrorEnvelope:
    def test_bad_request(self, client):
        resp = client.get("/bad-request")
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "BAD_REQUEST"
        assert body["message"] == "参数有误"
        assert body["data"] is None

    def test_not_found(self, client):
        resp = client.get("/not-found")
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_file_too_large_custom_code(self, client):
        resp = client.get("/file-too-large")
        assert resp.status_code == 400
        assert resp.json()["code"] == "FILE_TOO_LARGE"

    def test_upstream_502(self, client):
        resp = client.get("/upstream")
        assert resp.status_code == 502
        body = resp.json()
        assert body["code"] == "UPSTREAM_ERROR"
        assert body["details"]["upstream"] == "milvus"

    def test_exception_attributes(self):
        exc = UpstreamServiceError("x", upstream="kafka")
        assert exc.status_code == 502 and exc.code == "UPSTREAM_ERROR"
        base = AppError("fallback")
        assert base.status_code == 500 and base.code == "INTERNAL_ERROR"


class TestFrameworkErrors:
    def test_http_exception_wrapped(self, client):
        resp = client.get("/http-exc")
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "HTTP_ERROR"
        assert body["message"] == "未授权"

    def test_request_validation_422(self, client):
        resp = client.post("/validate", json={"text": "   "})
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "REQUEST_VALIDATION_FAILED"
        assert any("text" in e["field"] for e in body["details"]["errors"])

    def test_uncaught_500_sanitized(self, client):
        """未捕获异常返回脱敏消息，内部细节不外泄"""
        resp = client.get("/boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"
        assert "123456" not in resp.text


class TestFailHelper:
    def test_fail_with_details(self):
        payload = fail("X", "msg", details={"k": 1})
        assert payload["details"] == {"k": 1}

    def test_fail_without_details_omits_key(self):
        payload = fail("X", "msg")
        assert "details" not in payload
