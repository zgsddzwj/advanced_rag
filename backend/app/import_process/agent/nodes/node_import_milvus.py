"""
入库Milvus节点
确保集合存在（含BM25 Function）→ 幂等删除旧数据 → 批量插入Chunks
数据访问委托 app.repository.MilvusRepository（演进3）
"""
import sys

from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.repository.milvus_repository import get_milvus_repository
from app.core.logger import logger
from app.conf.settings import settings

# 批量插入大小
INSERT_BATCH_SIZE = 50


def node_import_milvus(state: ImportGraphState) -> ImportGraphState:
    """入库Milvus节点"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    add_running_task(state["task_id"], func_name)

    try:
        chunks = state.get("chunks") or []
        if not chunks:
            logger.warning("无有效切片数据，跳过入库")
            return state

        repository = get_milvus_repository()

        # 集合不存在则创建（含BM25 Function）
        collection_name = repository.ensure_chunks_collection(settings.embedding_dimension)

        # 幂等性处理：删除同一file_title的旧数据
        file_title = state.get("file_title", "")
        if file_title:
            repository.delete_by_file_title(file_title)
            logger.info(f"幂等性处理完成，已删除 file_title={file_title} 的旧数据")

        # 批量插入Chunks
        inserted_count = repository.insert_chunks(chunks, file_title, batch_size=INSERT_BATCH_SIZE)

        # 加载集合使数据可查
        from app.clients.milvus_utils import ensure_collection_loaded
        ensure_collection_loaded(repository.client, collection_name)
        logger.info(f"入库完成，共插入 {inserted_count} 条Chunk到集合 {collection_name}")

    except Exception as e:
        logger.error(f"入库Milvus失败: {str(e)}", exc_info=True)
    finally:
        add_done_task(state["task_id"], func_name)

    return state
