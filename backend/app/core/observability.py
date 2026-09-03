"""
可观测性中间件 + /metrics 端点（演进5）
================================================
ObservabilityMiddleware（每个 HTTP 请求）：
1. RequestID：读取上游 X-Request-ID 或生成 12 位短 ID，写入 contextvar，
   响应头回传（跨服务/日志检索链路）
2. 指标：http_requests_total{method,route,status} 计数 + 耗时 summary
3. 访问日志：method path status duration_ms（日志行自带 request_id）

register_metrics_endpoint：挂载 /metrics（Prometheus 文本格式，
非 /api 前缀、不走响应信封，供 Prometheus/调试直接抓取）
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from app.core.context import new_request_id, set_request_context
from app.core.logger import logger
from app.core import metrics


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """RequestID 注入 + 请求指标 + 访问日志"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        set_request_context(request_id, time.time() * 1000)
        start = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
        except Exception:
            # 异常最终由全局 handler 转 500；这里补充指标与日志
            metrics.inc_counter(
                "http_requests_total",
                {"method": method, "route": metrics.UNMATCHED, "status": "500"},
            )
            logger.exception(f"{method} {path} 500 (unhandled)")
            raise

        # 路由模板（匹配成功时 scope 中存在 route），避免原始 path 撑爆标签基数
        route = getattr(request.scope.get("route"), "path", None) or metrics.UNMATCHED
        status = str(response.status_code)
        duration_ms = (time.perf_counter() - start) * 1000

        metrics.inc_counter("http_requests_total", {"method": method, "route": route, "status": status})
        metrics.observe_duration(
            "http_request_duration_seconds",
            duration_ms / 1000,
            {"method": method, "route": route},
        )
        logger.info(f"{method} {path} {status} {duration_ms:.1f}ms")

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
        return response


def register_metrics_endpoint(app):
    """注册 /metrics（Prometheus 文本格式）"""

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics():
        return PlainTextResponse(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")
