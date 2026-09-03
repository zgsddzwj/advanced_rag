"""
Kafka 消费者（演进6 事件驱动强化）
后台常驻消费 document-events topic，事件驱动增量更新 Milvus chunks。

架构升级：
- 处理器注册表：事件 → 处理器的映射由 app/events/registry 声明式维护，
  消费主循环不含任何业务分支（开闭原则）
- 幂等消费：processed_events 集合记录已消费 event_id（TTL 自动过期），
  at-least-once 投递下重复消息自动跳过
- 可靠性：单事件指数重试；重试耗尽转入死信 topic（kafka_dlq_topic），
  并在元数据中标记 failed + last_error，杜绝坏消息卡死消费循环
- 可观测：kafka_events_total{type,outcome} 与处理耗时指标（app/core/metrics）
"""
import asyncio
import json
import time
from typing import Optional

from app.core.logger import logger
from app.core import metrics
from app.conf.settings import settings
from app.events.model import EventParseError, parse_event, get_handler
from app.events import handlers  # noqa: F401 — 导入即完成处理器注册
from app.repository.event_dedup_repository import get_event_dedup_repository
from app.repository.document_meta_repository import get_document_meta_repository

# 消费者全局状态
_consumer_task: Optional[asyncio.Task] = None
_should_stop = False


async def start_kafka_consumer():
    """启动 Kafka 消费者（在 FastAPI lifespan 中调用）"""
    global _consumer_task

    if not settings.kafka_enabled:
        logger.info("Kafka 未启用，消费者不启动")
        return

    _consumer_task = asyncio.create_task(_consume_loop())
    logger.info("Kafka 消费者后台任务已启动")


async def stop_kafka_consumer():
    """停止 Kafka 消费者（在 FastAPI lifespan 中调用）"""
    global _consumer_task, _should_stop

    if _consumer_task is None:
        return

    _should_stop = True
    _consumer_task.cancel()
    try:
        await asyncio.wait_for(_consumer_task, timeout=10)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    _consumer_task = None
    logger.info("Kafka 消费者已停止")


async def _consume_loop():
    """消费者主循环：连接 Kafka 并持续消费"""
    try:
        import aiokafka
    except ImportError:
        logger.warning("aiokafka 未安装，Kafka 消费者不可用")
        return

    # 等待 Kafka 就绪（最多重试 30 次）
    consumer = None
    for attempt in range(30):
        if _should_stop:
            return
        try:
            consumer = aiokafka.AIOKafkaConsumer(
                settings.kafka_topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_consumer_group,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
            )
            await consumer.start()
            logger.info(
                f"Kafka 消费者连接成功: {settings.kafka_bootstrap_servers}, "
                f"topic={settings.kafka_topic}, dlq={settings.kafka_dlq_topic}"
            )
            break
        except Exception as e:
            if attempt == 0:
                logger.info(f"等待 Kafka 就绪... ({e})")
            await asyncio.sleep(2)
    else:
        logger.error("Kafka 消费者连接超时（60s），放弃连接")
        return

    try:
        async for msg in consumer:
            if _should_stop:
                break
            # 无论成败都提交 offset：失败事件已重试并转入死信，不会因坏消息卡死
            await _process_message(msg.value)
            await consumer.commit()

    except asyncio.CancelledError:
        logger.info("Kafka 消费者收到取消信号")
    except Exception as e:
        logger.error(f"Kafka 消费者异常: {e}", exc_info=True)
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass
        logger.info("Kafka 消费者循环已退出")


async def _process_message(raw: dict):
    """
    处理单条消息：解析 → 幂等检查 → 线程池执行（含重试）→ 死信兜底
    任何失败路径都在本函数内闭环，保证调用方可安全提交 offset
    """
    # 1. 解析校验：坏消息直接死信，不重试
    try:
        event = parse_event(raw)
    except EventParseError as e:
        logger.error(f"丢弃非法事件: {e}")
        metrics.inc_counter("kafka_events_total", {"type": "invalid", "outcome": "dead_letter"})
        await _dead_letter_raw(raw, str(e))
        return

    labels = {"type": event.event_type, "outcome": "success"}

    # 2. 幂等检查：已成功消费的 event_id 直接跳过
    dedup = get_event_dedup_repository()
    if dedup.is_processed(event.event_id):
        logger.info(f"重复事件已跳过（幂等）: {event.event_type} {event.file_title} event={event.short_id()}")
        metrics.inc_counter("kafka_events_total", {"type": event.event_type, "outcome": "duplicate_skipped"})
        return

    # 3. 线程池执行（含指数重试）
    start = time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _execute_with_retry, event)
        metrics.observe_duration(
            "kafka_event_duration_seconds", time.perf_counter() - start, {"type": event.event_type}
        )
    except Exception as e:
        # 4. 重试耗尽 → 死信 + 元数据标记失败
        metrics.inc_counter("kafka_events_total", {"type": event.event_type, "outcome": "dead_letter"})
        await _dead_letter_raw(event.model_dump(), str(e), attempts=settings.kafka_event_retry_max)
        get_document_meta_repository().mark_failed(event.file_title, str(e))
        return

    # 5. 记录消费成功（幂等标记）
    dedup.mark_processed(event.event_id)
    metrics.inc_counter("kafka_events_total", labels)
    logger.info(f"事件处理成功: {event.event_type} | {event.file_title} | event={event.short_id()}")


def _execute_with_retry(event):
    """在线程池中同步执行处理器，按配置指数重试；最终失败抛出异常"""
    handler = get_handler(event.event_type)
    if handler is None:
        # 未注册的事件类型：跳过（记日志），视为已处理
        logger.warning(f"未知事件类型: {event.event_type}, 跳过 (event={event.short_id()})")
        return

    max_retry = settings.kafka_event_retry_max
    base_delay = settings.kafka_event_retry_delay_seconds

    for attempt in range(max_retry + 1):
        try:
            handler(event)
            return
        except Exception as e:
            if attempt == max_retry:
                logger.error(
                    f"事件处理彻底失败 (attempts={attempt + 1}): "
                    f"{event.event_type} {event.file_title}, {e}",
                    exc_info=True,
                )
                raise
            delay = min(base_delay * (2 ** attempt), 60.0)
            logger.warning(
                f"事件处理失败 (attempt {attempt + 1}/{max_retry + 1}): "
                f"{event.event_type} {event.file_title}, {delay:.1f}s 后重试, {e}"
            )
            time.sleep(delay)


async def _dead_letter_raw(payload: dict, error: str, attempts: int = 0):
    """将失败载荷投递到死信 topic"""
    from app.clients.kafka_producer import publish_to_dlq

    try:
        event = parse_event(payload)
    except EventParseError:
        # 载荷无法还原为事件模型 → 构造最小占位事件保证可追溯
        from app.events.model import DocumentEvent
        event = DocumentEvent(
            event_id=str(payload.get("event_id", "unknown")) or "unknown",
            event_type=str(payload.get("event_type", "unknown")),
            file_title=str(payload.get("file_title", "")),
        )
    await publish_to_dlq(event, error, attempts)
