"""
SSE 事件队列管理工具
基于 asyncio.Queue 实现每个 session 的消息推送
"""
import asyncio
import json
from enum import Enum
from typing import Dict, Any
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


def create_sse_queue(session_id: str):
    """为指定 session 创建 SSE 队列"""
    _sse_queues[session_id] = asyncio.Queue()
    logger.info(f"SSE 队列创建: {session_id}")


def push_to_session(session_id: str, event: SSEEvent, data: Dict[str, Any]):
    """向 session 的 SSE 队列推送事件"""
    if session_id not in _sse_queues:
        logger.warning(f"SSE 队列不存在: {session_id}，跳过推送")
        return

    try:
        _sse_queues[session_id].put_nowait({
            "event": event.value,
            "data": data
        })
    except asyncio.QueueFull:
        logger.warning(f"SSE 队列已满: {session_id}")


async def sse_generator(session_id: str, request=None):
    """
    SSE 事件生成器
    从队列消费事件，按 SSE 格式 yield
    """
    # 等待队列创建
    while session_id not in _sse_queues:
        await asyncio.sleep(0.1)

    queue = _sse_queues[session_id]

    # 检查客户端是否断开
    def is_disconnected():
        if request is not None:
            return request.is_disconnected()
        return False

    # 发送 ready 事件
    yield f"event: ready\ndata: {json.dumps({'session_id': session_id})}\n\n"

    while True:
        if is_disconnected():
            logger.info(f"SSE 客户端断开: {session_id}")
            break

        try:
            msg = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            # 发送心跳
            yield f": heartbeat\n\n"
            continue

        if msg is None:
            # 结束标记
            break

        event_name = msg["event"]
        data_str = json.dumps(msg["data"], ensure_ascii=False)
        yield f"event: {event_name}\ndata: {data_str}\n\n"

        if event_name == SSEEvent.FINAL.value or event_name == SSEEvent.ERROR.value:
            break

    # 清理队列
    if session_id in _sse_queues:
        del _sse_queues[session_id]
    logger.info(f"SSE 队列清理: {session_id}")
