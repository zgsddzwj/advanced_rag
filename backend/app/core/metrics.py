"""
进程内指标注册表（演进5：可观测性）
无外部依赖的轻量指标：计数器 / 直通量 / 耗时观测，支持标签维度。
线程安全（HTTP 中间件、SSE、后台线程、Kafka 消费者并发写入）。

暴露：
- /metrics 端点输出 Prometheus 文本格式（app/core/observability.py）
"""
import threading
import time
from collections import defaultdict
from typing import Dict, Tuple

_lock = threading.Lock()

# label_key -> value；label_key 形如 "http_requests_total|method=GET|path=/api/query/ask"
_counters: Dict[str, float] = {}
# label_key -> (sum, count, max)
_durations: Dict[str, Tuple[float, int, float]] = {}
# 标量 gauge
_gauges: Dict[str, float] = {}

# 路由归一化：未匹配路由的请求统一记为 unmatched，避免原始 path 爆炸标签
UNMATCHED = "unmatched"


def _label_key(name: str, labels: Dict[str, str]) -> str:
    if not labels:
        return name
    sorted_labels = "&".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{name}|{sorted_labels}"


def _to_prom_labels(label_str: str) -> str:
    """内部标签串 "k1=v1&k2=v2" → Prometheus 格式 'k1="v1",k2="v2"'"""
    if not label_str:
        return ""
    pairs = [
        f'{k.strip()}="{v.strip()}"'
        for k, v in (item.split("=", 1) for item in label_str.split("&"))
    ]
    return ",".join(pairs)


def _split_key(key: str) -> Tuple[str, str]:
    """内部指标键 → (指标名, prometheus 标签段)"""
    name, _, label_str = key.partition("|")
    return name, _to_prom_labels(label_str)


def inc_counter(name: str, labels: Dict[str, str] = None, value: float = 1.0):
    """计数器累加"""
    key = _label_key(name, labels or {})
    with _lock:
        _counters[key] = _counters.get(key, 0.0) + value


def inc_gauge(name: str, value: float = 1.0, labels: Dict[str, str] = None):
    """gauge 增加"""
    key = _label_key(name, labels or {})
    with _lock:
        _gauges[key] = _gauges.get(key, 0.0) + value


def dec_gauge(name: str, value: float = 1.0, labels: Dict[str, str] = None):
    """gauge 减少"""
    key = _label_key(name, labels or {})
    with _lock:
        _gauges[key] = _gauges.get(key, 0.0) - value


def set_gauge(name: str, value: float, labels: Dict[str, str] = None):
    """gauge 直接赋值"""
    key = _label_key(name, labels or {})
    with _lock:
        _gauges[key] = value


def observe_duration(name: str, seconds: float, labels: Dict[str, str] = None):
    """记录一次耗时观测（sum/count/max 聚合，进程内近似直方图）"""
    key = _label_key(name, labels or {})
    with _lock:
        total, count, max_v = _durations.get(key, (0.0, 0, 0.0))
        _durations[key] = (total + seconds, count + 1, max(max_v, seconds))


def snapshot() -> dict:
    """指标快照（health/日志用）"""
    with _lock:
        return {
            "counters": dict(_counters),
            "durations": {k: {"sum": v[0], "count": v[1], "max": v[2]} for k, v in _durations.items()},
            "gauges": dict(_gauges),
        }


def render_prometheus() -> str:
    """渲染 Prometheus 文本 exposition 格式"""
    lines = []
    ts_ms = int(time.time() * 1000)
    with _lock:
        counters = dict(_counters)
        durations = dict(_durations)
        gauges = dict(_gauges)

    def emit(labels: str, value) -> str:
        suffix = f"{{{labels}}}" if labels else ""
        return f"{suffix} {value} {ts_ms}"

    for key, value in counters.items():
        name, labels = _split_key(key)
        _emit_help(lines, name, "counter")
        lines.append(f"{name}{emit(labels, value)}")

    for key, (total, count, max_v) in durations.items():
        name, labels = _split_key(key)
        _emit_help(lines, name, "summary")
        for suffix, value in (("_sum", total), ("_count", count), ("_max", max_v)):
            lines.append(f"{name}{suffix}{emit(labels, value)}")

    for name, value in gauges.items():
        _emit_help(lines, name, "gauge")
        lines.append(f"{name}{emit('', value)}")

    return "\n".join(lines) + "\n"


def reset():
    """清空全部指标（测试用）"""
    with _lock:
        _counters.clear()
        _durations.clear()
        _gauges.clear()


# help 注释去重
_help_emitted = set()
_help_lock = threading.Lock()


def _emit_help(lines: list, name: str, metric_type: str):
    with _help_lock:
        if name not in _help_emitted:
            _help_emitted.add(name)
            lines.append(f"# HELP {name} NexusRAG {metric_type}")
            lines.append(f"# TYPE {name} {metric_type}")
