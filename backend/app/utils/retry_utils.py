"""
API 调用重试工具
为外部 API 调用（LLM、Embedding、Rerank 等）提供统一的重试机制
"""
import time
import functools
from typing import Callable, TypeVar, Any

from app.core.logger import logger

T = TypeVar("T")


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
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1}/{max_retries} 次重试，"
                        f"{delay:.1f}s 后执行，错误: {e}"
                    )
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
