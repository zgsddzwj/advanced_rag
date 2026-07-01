"""
SSE 事件队列管理工具
基于 asyncio.Queue 实现每个 session 的消息推送
支持跨线程推送（LangGraph 工作流在后台线程中运行）
"""
import asyncio
import json
from enum import Enum
from typing import Dict, Any, Optional
from app.core.logger import logger


class SSEEvent(Enum):
    """SSE 事件类型"""
    READY = "ready"
    PROGRESS = "progress"
    DELTA = "delta"
    FINAL = "final"
    ERROR = "error"


# 全局 SSE 队列字典：session_id → asyncio.Queue
_sse_queues: Dict[str, asyncio.Queue] = {}
# 全局事件循环字典：session_id → event_loop（用于跨线程推送）
_sse_loops: Dict[str, asyncio.AbstractEventLoop] = {}


def create_sse_queue(session_id: str, loop: Optional[asyncio.AbstractEventLoop] = None):
    """为指定 session 创建 SSE 队列"""
    if loop is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

    _sse_queues[session_id] = asyncio.Queue()
    _sse_loops[session_id] = loop
    logger.info(f"SSE 队列创建: {session_id}")


def push_to_session(session_id: str, event: SSEEvent, data: Dict[str, Any]):
    """
    向 session 的 SSE 队列推送事件（线程安全）
    支持从后台线程调用，通过 call_soon_threadsafe 转发到事件循环线程
    """
    if session_id not in _sse_queues:
        logger.warning(f"SSE 队列不存在: {session_id}，跳过推送")
        return

    msg = {"event": event.value, "data": data}
    loop = _sse_loops.get(session_id)

    try:
        if loop is not None and loop.is_running():
            # 从其他线程安全推送
            loop.call_soon_threadsafe(_sse_queues[session_id].put_nowait, msg)
        else:
            # 同线程直接推送
            _sse_queues[session_id].put_nowait(msg)
    except asyncio.QueueFull:
        logger.warning(f"SSE 队列已满: {session_id}")
    except RuntimeError:
        # 事件循环已关闭，直接推送
        try:
            _sse_queues[session_id].put_nowait(msg)
        except Exception:
            pass


async def sse_generator(session_id: str, request=None):
    """
    SSE 事件生成器
    从队列消费事件，按 SSE 格式 yield
    """
    # 等待队列创建
    wait_count = 0
    while session_id not in _sse_queues:
        await asyncio.sleep(0.1)
        wait_count += 1
        if wait_count > 100:  # 10 秒超时
            yield f"event: error\ndata: {json.dumps({'message': 'SSE 队列创建超时'})}\n\n"
            return

    queue = _sse_queues[session_id]

    # 发送 ready 事件
    yield f"event: ready\ndata: {json.dumps({'session_id': session_id})}\n\n"

    while True:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            # 发送心跳，同时检测客户端是否还在线
            try:
                yield f": heartbeat\n\n"
            except Exception:
                logger.info(f"SSE 客户端断开（心跳失败）: {session_id}")
                break
            continue

        if msg is None:
            # 结束标记
            break

        event_name = msg["event"]
        data_str = json.dumps(msg["data"], ensure_ascii=False)
        try:
            yield f"event: {event_name}\ndata: {data_str}\n\n"
        except Exception:
            logger.info(f"SSE 客户端断开（推送失败）: {session_id}")
            break

        if event_name == SSEEvent.FINAL.value or event_name == SSEEvent.ERROR.value:
            break

    # 清理队列和事件循环引用
    _sse_queues.pop(session_id, None)
    _sse_loops.pop(session_id, None)
    logger.info(f"SSE 队列清理: {session_id}")
