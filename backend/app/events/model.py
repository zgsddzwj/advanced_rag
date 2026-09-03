"""
文档事件域模型与处理器注册表（演进6）
================================================
事件驱动架构强化：
- DocumentEvent：pydantic 事件模型，消费前强校验，坏消息无法进入处理逻辑
- 处理器注册表：@register_handler(EVENT_ADD) 声明式注册，新增事件类型
  无需修改消费者主循环（开闭原则）
"""
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from pydantic import BaseModel, Field

# 事件类型常量
EVENT_ADD = "DOCUMENT_ADD"
EVENT_UPDATE = "DOCUMENT_UPDATE"
EVENT_DELETE = "DOCUMENT_DELETE"

# 处理器签名：同步函数（消费者在线程池中执行）
HandlerType = Callable[["DocumentEvent"], None]


class DocumentEvent(BaseModel):
    """document-events topic 的事件载荷"""

    event_id: str
    event_type: str
    file_title: str
    file_path: str = ""
    content_hash: str = ""
    timestamp: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    def short_id(self) -> str:
        return self.event_id[:8]


class EventParseError(ValueError):
    """事件载荷非法（无法解析/缺字段），应直接进入死信而不重试"""


def build_event(
    event_type: str,
    file_title: str,
    file_path: str = "",
    content_hash: str = "",
    chunk_count: int = 0,
    item_name: str = "",
) -> DocumentEvent:
    """构建新事件（生产者侧统一入口，自动生成 event_id 与时间戳）"""
    return DocumentEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        file_title=file_title,
        file_path=file_path,
        content_hash=content_hash,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"chunk_count": chunk_count, "item_name": item_name},
    )


def parse_event(raw: dict) -> DocumentEvent:
    """解析并校验原始消息；非法载荷抛出 EventParseError"""
    try:
        return DocumentEvent.model_validate(raw)
    except Exception as e:
        raise EventParseError(f"事件载荷非法: {e}") from e


# ============================================================
#  处理器注册表
# ============================================================

_HANDLERS: Dict[str, HandlerType] = {}


def register_handler(event_type: str) -> Callable[[HandlerType], HandlerType]:
    """声明式注册事件处理器：@register_handler(EVENT_ADD)"""

    def decorator(fn: HandlerType) -> HandlerType:
        if event_type in _HANDLERS:
            raise ValueError(f"事件处理器重复注册: {event_type}")
        _HANDLERS[event_type] = fn
        return fn

    return decorator


def get_handler(event_type: str) -> Optional[HandlerType]:
    """按事件类型取处理器；未注册返回 None"""
    return _HANDLERS.get(event_type)


def registered_types() -> list:
    return sorted(_HANDLERS.keys())
