"""
优化3 单元测试：访问日志降噪
/metrics 与 /api/health 不再逐条记录访问日志，业务路由照常记录；指标不受影响
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import metrics
from app.core.logger import logger
from app.core.observability import ObservabilityMiddleware, register_metrics_endpoint


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def captured_logs():
    """挂载日志捕获 sink，收集本用例期间的全部日志文本"""
    lines = []
    handler_id = logger.add(lines.append, level="INFO")
    yield lines
    logger.remove(handler_id)


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)
    register_metrics_endpoint(app)

    @app.get("/api/hello")
    async def hello():
        return {"ok": True}

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


class TestAccessLogNoise:
    def test_business_route_logged(self, captured_logs):
        client = TestClient(build_app())
        client.get("/api/hello")
        assert any("GET /api/hello 200" in line for line in captured_logs)

    def test_metrics_endpoint_not_logged(self, captured_logs):
        client = TestClient(build_app())
        client.get("/metrics")
        assert not any("GET /metrics" in line for line in captured_logs)

    def test_health_endpoint_not_logged(self, captured_logs):
        client = TestClient(build_app())
        client.get("/api/health")
        assert not any("GET /api/health" in line for line in captured_logs)

    def test_exclusion_is_exact_match(self, captured_logs):
        """排除仅对精确路径生效，其他 /api/* 路由不受影响"""
        client = TestClient(build_app())
        client.get("/api/hello")
        client.get("/metrics")
        client.get("/api/health")
        # 同一批请求中，业务路由有日志、被排除端点无日志
        assert any("GET /api/hello 200" in line for line in captured_logs)
        assert not any("GET /metrics" in line for line in captured_logs)
        assert not any("GET /api/health" in line for line in captured_logs)

    def test_metrics_counters_still_recorded(self, captured_logs):
        """降噪只影响访问日志，指标照常上报"""
        client = TestClient(build_app())
        client.get("/metrics")
        snap = metrics.snapshot()["counters"]
        assert any("/metrics" in key for key in snap)
