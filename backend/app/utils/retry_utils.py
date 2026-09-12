"""
API 调用重试工具
为外部 API 调用（LLM、Embedding、Rerank 等）提供统一的重试机制
"""
import time
import random
import functools
from typing import Callable, TypeVar

from app.core.logger import logger

T = TypeVar("T")


def compute_backoff_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """
    计算指数退避等待秒数（等量抖动 equal jitter）：
    基础值 = min(base * 2^attempt, max)，实际值在 [基础值/2, 基础值] 内随机。
    固定间隔会让多实例/多事件在故障恢复瞬间按同一节奏同步重试（重试风暴），
    抖动将其打散。
    """
    base = min(base_delay * (2 ** attempt), max_delay)
    return base / 2 + random.uniform(0, base / 2)


def _sleep_between_retries(delay: float):
    """
    重试间隔等待（同步阻塞 sleep）

    with_retry 包装的是同步阻塞函数，等待本身无法真正异步化。
    此前实现在事件循环线程中使用 run_coroutine_threadsafe + future.result()
    等待 asyncio.sleep，会在同一线程上相互等待（等待事件循环调度协程，
    而事件循环又被本线程阻塞），必然死锁直至超时（delay+5s）后抛出
    TimeoutError，导致每次重试都空等且多消耗一轮重试。
    统一改为 time.sleep，行为正确且无额外开销。
    """
    time.sleep(delay)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    装饰器：为函数添加指数退避重试机制
    :param max_retries: 最大重试次数
    :param base_delay: 基础延迟（秒）
    :param max_delay: 最大延迟上限（秒）
    :param exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} 重试 {max_retries} 次后仍失败: {e}"
                        )
                        raise
                    delay = compute_backoff_delay(attempt, base_delay, max_delay)
                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1}/{max_retries} 次重试，"
                        f"{delay:.1f}s 后执行，错误: {e}"
                    )
                    _sleep_between_retries(delay)
            raise last_exception
        return wrapper
    return decorator
