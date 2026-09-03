"""
文档事件处理器（演进6）
从 kafka_consumer 中解耦：每种事件类型一个处理器，声明式注册。
处理器为同步函数（消费者在线程池执行），数据访问全部委托仓储。
"""
import uuid

from app.conf.settings import settings
from app.core.logger import logger
from app.events.model import (
    DocumentEvent, EVENT_ADD, EVENT_DELETE, EVENT_UPDATE, register_handler,
)
from app.repository.document_meta_repository import get_document_meta_repository
from app.repository.milvus_repository import get_milvus_repository
from app.utils.path_util import PROJECT_ROOT


@register_handler(EVENT_ADD)
def handle_add(event: DocumentEvent):
    """处理文档新增事件：触发完整导入流程"""
    logger.info(f"[ADD] 开始导入: {event.file_title} (event={event.short_id()})")
    get_document_meta_repository().mark_status(event.file_title, "syncing")

    _run_import_graph(event)

    get_document_meta_repository().mark_status(event.file_title, "active")
    logger.info(f"[ADD] 导入完成: {event.file_title}")


@register_handler(EVENT_UPDATE)
def handle_update(event: DocumentEvent):
    """处理文档变更事件：先删旧 chunks，再重新导入"""
    logger.info(f"[UPDATE] 开始更新: {event.file_title} (event={event.short_id()})")
    get_document_meta_repository().mark_status(event.file_title, "syncing")

    # Step 1: 删除 Milvus 中的旧 chunks
    get_milvus_repository().delete_by_file_title(event.file_title)
    logger.info(f"[UPDATE] 旧 chunks 已删除: {event.file_title}")

    # Step 2: 重新导入
    _run_import_graph(event)

    get_document_meta_repository().mark_status(event.file_title, "active")
    logger.info(f"[UPDATE] 更新完成: {event.file_title}")


@register_handler(EVENT_DELETE)
def handle_delete(event: DocumentEvent):
    """处理文档删除事件：清除 Milvus chunks + item_names + 元数据"""
    logger.info(f"[DELETE] 开始删除: {event.file_title} (event={event.short_id()})")

    get_milvus_repository().delete_by_file_title(event.file_title)
    get_milvus_repository().delete_item_names_by_file_title(event.file_title)
    get_document_meta_repository().delete(event.file_title)

    logger.info(f"[DELETE] 删除完成: {event.file_title}")


def _run_import_graph(event: DocumentEvent):
    """
    触发 LangGraph 导入流程（复用 kb_import_app，当前线程同步执行）
    失败时抛出异常，由消费者的重试/死信机制接管
    """
    import os

    from app.import_process.agent.main_graph import kb_import_app
    from app.import_process.agent.state import create_default_state
    from app.utils.task_utils import (
        update_task_status, TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
    )
    from app.clients.document_meta_utils import compute_content_hash

    task_id = f"kafka_{uuid.uuid4().hex[:8]}"
    output_dir = str(PROJECT_ROOT / "output" / f"{task_id}_{event.file_title}")

    os.makedirs(output_dir, exist_ok=True)
    update_task_status(task_id, TASK_STATUS_PROCESSING)

    try:
        initial_state = create_default_state(
            task_id=task_id,
            local_file_path=event.file_path,
            local_dir=output_dir,
        )
        result = kb_import_app.invoke(initial_state)

        chunks = result.get("chunks", [])
        item_name = result.get("item_name", "")
        content_hash = compute_content_hash(event.file_path)

        get_document_meta_repository().upsert(
            file_title=event.file_title,
            content_hash=content_hash,
            chunk_count=len(chunks),
            item_name=item_name,
            file_path=event.file_path,
        )

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(
            f"Kafka 触发导入完成: {event.file_title}, chunks={len(chunks)}, task_id={task_id}"
        )

    except Exception as e:
        logger.error(f"Kafka 触发导入失败: {event.file_title}, {e}", exc_info=True)
        update_task_status(task_id, TASK_STATUS_FAILED)
        raise
