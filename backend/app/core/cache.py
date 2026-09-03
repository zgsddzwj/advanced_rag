"""
多级缓存层（演进8）
================================================
进程内 TTL + LRU 缓存，带容量上限与命中统计：
- 线程安全（RLock）：HTTP 中间件 / LangGraph 节点 / Kafka 消费者并发访问
- LRU 驱逐：容量满时淘汰最久未使用条目
- TTL 过期：单调时钟计时，不受系统时间跳变影响
- 指标集成：命中/未命中计数与条目数 gauge 自动上报 /metrics
- 注册表：命名缓存统一登记，/api/health 输出各缓存统计

使用方：app/core/cache.get_cache("embedding") 等；缓存实例由各模块注册。
"""
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple

from app.core import metrics
from app.core.logger import logger


class TTLCache:
    """线程安全的 TTL + LRU 缓存"""

    def __init__(self, name: str, maxsize: int = 1024, ttl: float = 3600.0):
        if maxsize < 1:
            raise ValueError("maxsize 必须 >= 1")
        if ttl <= 0:
            raise ValueError("ttl 必须 > 0")
        self.name = name
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: "OrderedDict[Any, Tuple[float, Any]]" = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ---------- 基础操作 ----------

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self._misses += 1
                self._report_metrics(hit=False)
                return default
            expires_at, value = item
            if time.monotonic() >= expires_at:
                # 过期条目即时淘汰
                del self._data[key]
                self._misses += 1
                self._report_metrics(hit=False)
                return default
            # 命中：移到队首（LRU）
            self._data.move_to_end(key)
            self._hits += 1
            self._report_metrics(hit=True)
            return value

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)
                self._evictions += 1
            self._report_metrics()

    def delete(self, key: Any) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._report_metrics()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._report_metrics()

    def get_or_set(self, key: Any, factory: Callable[[], Any]) -> Any:
        """
        原子化 get-or-set：命中直接返回；未命中调用 factory（锁外执行，避免长任务阻塞）
        并发未命中时 factory 可能执行多次（last-write-wins），对幂等 factory 安全
        """
        value = self.get(key, _SENTINEL)
        if value is not _SENTINEL:
            return value
        value = factory()
        self.set(key, value)
        return value

    # ---------- 统计 ----------

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "name": self.name,
                "size": len(self._data),
                "maxsize": self.maxsize,
                "ttl": self.ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 4) if total else 0.0,
                "evictions": self._evictions,
            }

    def _report_metrics(self, hit: Optional[bool] = None):
        if hit is True:
            metrics.inc_counter("cache_hits_total", {"cache": self.name})
        elif hit is False:
            metrics.inc_counter("cache_misses_total", {"cache": self.name})
        metrics.set_gauge("cache_entries", len(self._data), labels={"cache": self.name})


_SENTINEL = object()


# ============================================================
#  缓存注册表
# ============================================================

_caches: Dict[str, TTLCache] = {}
_registry_lock = threading.RLock()


def register_cache(name: str, maxsize: int, ttl: float) -> TTLCache:
    """注册命名缓存（同名返回既有实例，便于模块级单例）"""
    with _registry_lock:
        if name in _caches:
            return _caches[name]
        cache = TTLCache(name, maxsize=maxsize, ttl=ttl)
        _caches[name] = cache
        logger.info(f"缓存注册: {name} (maxsize={maxsize}, ttl={ttl}s)")
        return cache


def get_cache(name: str) -> Optional[TTLCache]:
    with _registry_lock:
        return _caches.get(name)


def all_caches() -> Dict[str, TTLCache]:
    with _registry_lock:
        return dict(_caches)


def all_stats() -> Dict[str, Dict[str, Any]]:
    return {name: cache.stats() for name, cache in all_caches().items()}
