"""
Kafka 消费者
后台常驻消费 document-events topic，根据事件类型实时增量更新 Milvus chunks。

事件处理逻辑：
  DOCUMENT_ADD:    触发完整 LangGraph 导入流程 → 入库 Milvus
  DOCUMENT_UPDATE: 先删 Milvus 旧 chunks → 再触发导入流程
  DOCUMENT_DELETE: 删除 Milvus 中该 file_title 的所有 chunks + item_names + 元数据
"""
import asyncio
import json
import os
import uuid
import threading
from typing import Optional

from app.core.logger import logger
from app.clients.milvus_utils import get_milvus_client
from app.clients.document_meta_utils import (
    mark_status,
    delete_metadata,
    get_metadata,
)
from app.utils.escape_milvus_string_utils import escape_milvus_string
from app.utils.path_util import PROJECT_ROOT
from app.conf.settings import settings

# 消费者全局状态
_consumer_task: Optional[asyncio.Task] = None
_consumer_thread: Optional[threading.Thread] = None
_should_stop = False

# 错误重试配置
MAX_RETRY = 3
RETRY_DELAY_SECONDS = 5


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
            logger.info(f"Kafka 消费者连接成功: {settings.kafka_bootstrap_servers}, topic={settings.kafka_topic}")
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

            try:
                await _process_event(msg.value)
                await consumer.commit()
            except Exception as e:
                logger.error(f"事件处理失败，跳过: {e}", exc_info=True)
                # 提交 offset 避免卡住，错误已记录
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


async def _process_event(event: dict):
    """处理单个 Kafka 事件（在线程池中执行同步逻辑）"""
    event_type = event.get("event_type", "")
    file_title = event.get("file_title", "")
    file_path = event.get("file_path", "")
    event_id = event.get("event_id", "")[:8]

    logger.info(f"收到 Kafka 事件: {event_type} | {file_title} | event_id={event_id}")

    # 在线程池中执行同步的 Milvus / LangGraph 操作
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _handle_event_sync,
        event_type,
        file_title,
        file_path,
    )


def _handle_event_sync(event_type: str, file_title: str, file_path: str):
    """同步处理事件（在线程池中执行）"""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            if event_type == "DOCUMENT_ADD":
                _handle_add(file_title, file_path)
            elif event_type == "DOCUMENT_UPDATE":
                _handle_update(file_title, file_path)
            elif event_type == "DOCUMENT_DELETE":
                _handle_delete(file_title)
            else:
                logger.warning(f"未知事件类型: {event_type}, 跳过")
            return  # 成功则退出
        except Exception as e:
            logger.error(
                f"事件处理失败 (attempt {attempt}/{MAX_RETRY}): "
                f"{event_type} {file_title}, {e}",
                exc_info=True,
            )
            if attempt < MAX_RETRY:
                import time
                time.sleep(RETRY_DELAY_SECONDS)

    logger.error(f"事件处理彻底失败，放弃: {event_type} {file_title}")


# ============================================================
#  事件处理逻辑
# ============================================================

def _handle_add(file_title: str, file_path: str):
    """处理文档新增事件：触发完整导入流程"""
    logger.info(f"[ADD] 开始导入: {file_title}")
    mark_status(file_title, "syncing")

    _run_import_graph(file_title, file_path)

    # 更新状态为 active
    mark_status(file_title, "active")
    logger.info(f"[ADD] 导入完成: {file_title}")


def _handle_update(file_title: str, file_path: str):
    """处理文档变更事件：先删旧 chunks，再重新导入"""
    logger.info(f"[UPDATE] 开始更新: {file_title}")
    mark_status(file_title, "syncing")

    # Step 1: 删除 Milvus 中的旧 chunks
    _delete_chunks_from_milvus(file_title)
    logger.info(f"[UPDATE] 旧 chunks 已删除: {file_title}")

    # Step 2: 重新导入
    _run_import_graph(file_title, file_path)

    mark_status(file_title, "active")
    logger.info(f"[UPDATE] 更新完成: {file_title}")


def _handle_delete(file_title: str):
    """处理文档删除事件：清除 Milvus chunks + item_names + 元数据"""
    logger.info(f"[DELETE] 开始删除: {file_title}")

    # Step 1: 删除 Milvus chunks
    _delete_chunks_from_milvus(file_title)

    # Step 2: 删除 Milvus item_names
    _delete_item_names_from_milvus(file_title)

    # Step 3: 删除 MongoDB 元数据
    delete_metadata(file_title)

    logger.info(f"[DELETE] 删除完成: {file_title}")


# ============================================================
#  Milvus 操作
# ============================================================

def _delete_chunks_from_milvus(file_title: str):
    """从 kb_chunks 集合中删除指定 file_title 的所有 chunks"""
    try:
        client = get_milvus_client()
        collection_name = settings.chunks_collection

        if not client.has_collection(collection_name=collection_name):
            logger.warning(f"集合 {collection_name} 不存在，跳过删除")
            return

        client.load_collection(collection_name=collection_name)
        safe_title = escape_milvus_string(file_title)
        client.delete(
            collection_name=collection_name,
            filter=f'file_title=="{safe_title}"',
        )
        logger.info(f"已从 {collection_name} 删除 file_title={file_title} 的 chunks")

    except Exception as e:
        logger.error(f"从 Milvus 删除 chunks 失败: {file_title}, {e}")
        raise


def _delete_item_names_from_milvus(file_title: str):
    """从 kb_item_names 集合中删除指定 file_title 的记录"""
    try:
        client = get_milvus_client()
        collection_name = settings.item_names_collection

        if not client.has_collection(collection_name=collection_name):
            logger.warning(f"集合 {collection_name} 不存在，跳过删除")
            return

        client.load_collection(collection_name=collection_name)
        safe_title = escape_milvus_string(file_title)
        client.delete(
            collection_name=collection_name,
            filter=f'file_title=="{safe_title}"',
        )
        logger.info(f"已从 {collection_name} 删除 file_title={file_title} 的记录")

    except Exception as e:
        logger.error(f"从 Milvus 删除 item_names 失败: {file_title}, {e}")
        raise


# ============================================================
#  LangGraph 导入流程
# ============================================================

def _run_import_graph(file_title: str, file_path: str):
    """
    触发 LangGraph 导入流程
    复用现有的 kb_import_app，在当前线程同步执行
    """
    # 延迟导入，避免循环依赖
    from app.import_process.agent.main_graph import kb_import_app
    from app.import_process.agent.state import create_default_state
    from app.utils.task_utils import update_task_status, TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED

    task_id = f"kafka_{uuid.uuid4().hex[:8]}"
    output_dir = str(PROJECT_ROOT / "output" / f"{task_id}_{file_title}")

    os.makedirs(output_dir, exist_ok=True)

    update_task_status(task_id, TASK_STATUS_PROCESSING)

    try:
        initial_state = create_default_state(
            task_id=task_id,
            local_file_path=file_path,
            local_dir=output_dir,
        )

        result = kb_import_app.invoke(initial_state)

        # 获取导入结果
        chunks = result.get("chunks", [])
        item_name = result.get("item_name", "")
        chunk_count = len(chunks)

        # 更新元数据
        from app.clients.document_meta_utils import upsert_metadata, compute_content_hash
        content_hash = compute_content_hash(file_path)
        upsert_metadata(
            file_title=file_title,
            content_hash=content_hash,
            chunk_count=chunk_count,
            item_name=item_name,
            file_path=file_path,
        )

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(
            f"Kafka 触发导入完成: {file_title}, chunks={chunk_count}, "
            f"item_name={item_name}, task_id={task_id}"
        )

    except Exception as e:
        logger.error(f"Kafka 触发导入失败: {file_title}, {e}", exc_info=True)
        update_task_status(task_id, TASK_STATUS_FAILED)
        raise
