"""
健康聚合（演进5，优化2：探活结果短缓存）
================================================
/api/health 对全部下游依赖做一次轻量探活，汇总为整体状态：
- ok        所有依赖可达
- degraded  部分依赖不可达（不影响进程存活，交由告警/前端提示处理）
探活永不抛异常、单依赖限时，保证端点本身始终快速可用。

探活结果默认缓存 10 秒：Prometheus/前端高频抓取时不会反复冲击下游
（health 属于只读观测端点，短缓存不影响故障发现速度的量级），
响应中的 cached 字段标明是否来自缓存。
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple

from app.core.logger import logger
from app.conf.settings import settings

# 单依赖探活超时（秒）
CHECK_TIMEOUT_SECONDS = 5
# 探活结果缓存时长（秒）
HEALTH_CACHE_TTL_SECONDS = 10

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="healthcheck")

# 探活结果缓存（演进2 优化：读多写少，逐出由 TTL 决定）
_health_cache: Dict = {"data": None, "expires_at": 0.0}
_health_lock = threading.Lock()


def _check_mongo() -> Tuple[bool, str]:
    from app.repository.mongo_connection import get_mongo_client
    client = get_mongo_client()
    client.admin.command("ping")
    return True, "ping ok"


def _check_milvus() -> Tuple[bool, str]:
    from app.repository.milvus_repository import get_milvus_repository
    repo = get_milvus_repository()
    if not repo.has_collection(settings.chunks_collection):
        return True, "集合未创建（尚未导入文档）"
    return True, "ok"


def _check_minio() -> Tuple[bool, str]:
    from app.clients.minio_utils import get_minio_client
    client = get_minio_client()
    if not client.bucket_exists(settings.minio_bucket_name):
        return False, f"bucket 不存在: {settings.minio_bucket_name}"
    return True, "ok"


def _check_kafka() -> Tuple[bool, str]:
    if not settings.kafka_enabled:
        return True, "disabled"
    from app.clients.kafka_producer import get_producer_state
    state = get_producer_state()
    if state == "unknown":
        return True, "未初始化（尚无事件发布）"
    return (state == "running"), f"producer={state}"


_CHECKS = {
    "mongo": _check_mongo,
    "milvus": _check_milvus,
    "minio": _check_minio,
    "kafka": _check_kafka,
}


def collect_health(force_refresh: bool = False) -> Dict:
    """
    返回健康聚合结果；默认命中 10s 内的缓存，force_refresh=True 强制重新探活
    响应额外携带 cached 字段标明数据来源
    """
    now = time.monotonic()
    if not force_refresh:
        with _health_lock:
            cached = _health_cache["data"]
            if cached is not None and now < _health_cache["expires_at"]:
                result = dict(cached)
                result["cached"] = True
                return result

    result = _probe_all()
    with _health_lock:
        _health_cache["data"] = result
        _health_cache["expires_at"] = time.monotonic() + HEALTH_CACHE_TTL_SECONDS

    out = dict(result)
    out["cached"] = False
    return out


def _probe_all() -> Dict:
    """
    并发探活全部依赖，返回：
    {status, checks: {name: {ok, detail, elapsed_ms}}, caches: {...}}
    """
    def run(name, fn):
        start = time.perf_counter()
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        return name, {
            "ok": ok,
            "detail": detail,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
        }

    results = {}
    futures = [_executor.submit(run, name, fn) for name, fn in _CHECKS.items()]
    for future in futures:
        try:
            name, result = future.result(timeout=CHECK_TIMEOUT_SECONDS)
            results[name] = result
        except Exception:
            results["<timeout>"] = {"ok": False, "detail": "health check timeout", "elapsed_ms": CHECK_TIMEOUT_SECONDS * 1000}

    all_ok = all(c["ok"] for c in results.values())
    if not all_ok:
        logger.warning(f"健康检查发现异常依赖: {[k for k, v in results.items() if not v['ok']]}")

    # 缓存统计（演进8）：命中率/条目数等，便于容量与效果观察
    from app.core import app_caches  # noqa: F401 — 导入即注册全部命名缓存
    from app.core.cache import all_stats as cache_all_stats

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": results,
        "caches": cache_all_stats(),
    }
