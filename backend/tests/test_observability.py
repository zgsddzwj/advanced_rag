"""
演进5 单元测试：可观测性
指标注册表、ObservabilityMiddleware（RequestID + 指标 + 访问日志）、/metrics 渲染
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import metrics
from app.core.context import get_request_id, request_id_var
from app.core.observability import ObservabilityMiddleware, register_metrics_endpoint


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)
    register_metrics_endpoint(app)

    @app.get("/api/hello")
    async def hello():
        return {"request_id": get_request_id()}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("x")

    return app


class TestMetricsRegistry:
    def test_counter(self):
        metrics.inc_counter("demo_total", {"a": "1"})
        metrics.inc_counter("demo_total", {"a": "1"}, value=2)
        metrics.inc_counter("demo_total", {"a": "2"})
        snap = metrics.snapshot()["counters"]
        assert snap["demo_total|a=1"] == 3.0
        assert snap["demo_total|a=2"] == 1.0

    def test_gauge(self):
        metrics.inc_gauge("g")
        metrics.inc_gauge("g")
        metrics.dec_gauge("g")
        assert metrics.snapshot()["gauges"]["g"] == 1.0
        metrics.set_gauge("g", 42)
        assert metrics.snapshot()["gauges"]["g"] == 42

    def test_duration(self):
        metrics.observe_duration("d", 0.1)
        metrics.observe_duration("d", 0.5)
        d = metrics.snapshot()["durations"]["d"]  # 无标签时键为裸指标名
        assert d["count"] == 2
        assert abs(d["sum"] - 0.6) < 1e-9
        assert d["max"] == 0.5

    def test_prometheus_render(self):
        metrics.inc_counter("http_requests_total", {"method": "GET", "route": "/x", "status": "200"})
        metrics.inc_gauge("sse_active_queues", 3)
        text = metrics.render_prometheus()
        assert 'http_requests_total{method="GET",route="/x",status="200"} 1' in text
        assert "sse_active_queues 3" in text
        assert "# TYPE http_requests_total counter" in text


class TestObservabilityMiddleware:
    def test_request_id_generated_and_echoed(self):
        client = TestClient(build_app())
        resp = client.get("/api/hello")
        assert resp.status_code == 200
        rid = resp.headers["X-Request-ID"]
        assert len(rid) == 12
        # 处理函数内读取的 request_id 与响应头一致
        assert resp.json()["request_id"] == rid

    def test_upstream_request_id_preserved(self):
        client = TestClient(build_app())
        resp = client.get("/api/hello", headers={"X-Request-ID": "my-trace-id-123"})
        assert resp.headers["X-Request-ID"] == "my-trace-id-123"

    def test_process_time_header(self):
        client = TestClient(build_app())
        resp = client.get("/api/hello")
        assert "X-Process-Time-Ms" in resp.headers

    def test_metrics_recorded(self):
        client = TestClient(build_app())
        client.get("/api/hello")
        snap = metrics.snapshot()["counters"]
        assert snap.get('http_requests_total|method=GET&path=UNMATCHED&route=/api/hello&status=200') is None
        # route 标签使用路由模板而非原始 path
        assert snap.get('http_requests_total|method=GET&route=/api/hello&status=200') == 1.0

    def test_metrics_endpoint(self):
        client = TestClient(build_app())
        client.get("/api/hello")
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "http_requests_total" in resp.text


class TestRequestContext:
    def test_default_request_id(self):
        assert get_request_id() == "-"

    def test_context_isolation(self):
        token = request_id_var.set("abc")
        assert get_request_id() == "abc"
        request_id_var.reset(token)
        assert get_request_id() == "-"
