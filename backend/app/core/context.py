"""
请求上下文（演进5：可观测性）
基于 contextvars 的请求级上下文，跨线程/协程安全。
RequestID 中间件在请求入口写入，日志 patch 与指标标签在任意位置读取。
"""
import uuid
from contextvars import ContextVar

# 当前请求 ID（未经过 HTTP 中间件的后台任务/Kafka 线程中为 "-"）
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# 每请求起点时间（毫秒），用于任意位置记录相对耗时
_start_time_var: ContextVar[float] = ContextVar("request_start_ms", default=0.0)


def new_request_id() -> str:
    """生成 12 位短请求 ID"""
    return uuid.uuid4().hex[:12]


def set_request_context(request_id: str, start_ms: float) -> None:
    """写入请求上下文（仅中间件调用）"""
    request_id_var.set(request_id)
    _start_time_var.set(start_ms)


def get_request_id() -> str:
    """读取当前请求 ID"""
    return request_id_var.get()
