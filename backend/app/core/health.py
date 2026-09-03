"""
健康聚合（演进5）
================================================
/api/health 对全部下游依赖做一次轻量探活，汇总为整体状态：
- ok        所有依赖可达
- degraded  部分依赖不可达（不影响进程存活，交由告警/前端提示处理）
探活永不抛异常、单依赖限时，保证端点本身始终快速可用。
"""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple

from app.core.logger import logger
from app.conf.settings import settings

# 单依赖探活超时（秒）
CHECK_TIMEOUT_SECONDS = 5

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="healthcheck")


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


def collect_health() -> Dict:
    """
    并发探活全部依赖，返回：
    {status, checks: {name: {ok, detail, elapsed_ms}}}
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

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": results,
    }
