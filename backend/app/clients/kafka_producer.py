"""
Kafka 生产者
发布文档变更事件到 Kafka topic，支持 ADD / UPDATE / DELETE 三种事件类型。
使用 aiokafka 异步发送，与 FastAPI 异步模型无缝集成。
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.logger import logger
from app.conf.settings import settings

# 延迟导入 aiokafka，避免未安装时启动崩溃
_producer = None
_aiokafka = None
# 生产者状态：unknown / running / failed / stopped（健康检查用）
_producer_state = "unknown"


def get_producer_state() -> str:
    """返回生产者当前状态（unknown=尚未初始化）"""
    return _producer_state


async def _get_producer():
    """延迟初始化 Kafka 生产者单例"""
    global _producer, _aiokafka, _producer_state
    if _producer is not None:
        return _producer

    try:
        import aiokafka
        _aiokafka = aiokafka
    except ImportError:
        logger.warning("aiokafka 未安装，Kafka 生产者不可用")
        return None

    try:
        _producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
            retry_backoff_ms=500,
            request_timeout_ms=10000,
        )
        await _producer.start()
        _producer_state = "running"
        logger.info(f"Kafka 生产者连接成功: {settings.kafka_bootstrap_servers}")
    except Exception as e:
        logger.error(f"Kafka 生产者连接失败: {e}")
        _producer = None
        _producer_state = "failed"
        return None

    return _producer


async def publish_document_event(
    event_type: str,
    file_title: str,
    file_path: str = "",
    content_hash: str = "",
    chunk_count: int = 0,
    item_name: str = "",
):
    """
    发布文档变更事件到 Kafka

    :param event_type: DOCUMENT_ADD / DOCUMENT_UPDATE / DOCUMENT_DELETE
    :param file_title: 文档标题（唯一标识）
    :param file_path: 文件路径（ADD/UPDATE 时需要）
    :param content_hash: 文件内容哈希
    :param chunk_count: chunk 数量
    :param item_name: 文档主题
    """
    if not settings.kafka_enabled:
        logger.debug(f"Kafka 未启用，跳过事件发布: {event_type} {file_title}")
        return False

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "file_title": file_title,
        "file_path": file_path,
        "content_hash": content_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "chunk_count": chunk_count,
            "item_name": item_name,
        },
    }

    try:
        producer = await _get_producer()
        if producer is None:
            logger.warning(f"Kafka 生产者不可用，事件未发布: {event_type} {file_title}")
            return False

        await producer.send_and_wait(
            topic=settings.kafka_topic,
            key=file_title,
            value=event,
        )
        logger.info(f"Kafka 事件已发布: {event_type} | {file_title} | event_id={event['event_id'][:8]}")
        return True

    except Exception as e:
        logger.error(f"Kafka 事件发布失败: {event_type} {file_title}, {e}")
        return False


async def close_producer():
    """关闭 Kafka 生产者"""
    global _producer, _producer_state
    if _producer is not None:
        try:
            await _producer.stop()
            logger.info("Kafka 生产者已关闭")
        except Exception as e:
            logger.error(f"关闭 Kafka 生产者异常: {e}")
        finally:
            _producer = None
            _producer_state = "stopped"
