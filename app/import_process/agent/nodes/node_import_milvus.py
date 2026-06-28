"""
入库Milvus节点
创建集合（含BM25 Function）→ 批量插入Chunks → 写入ItemNames
"""
import os
import sys
from typing import List, Dict, Any

from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.clients.milvus_utils import get_milvus_client, create_chunks_collection
from app.utils.escape_milvus_string_utils import escape_milvus_string
from app.conf.milvus_config import milvus_config
from app.conf.lm_config import lm_config
from app.core.logger import logger

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

        collection_name = milvus_config.CHUNKS_COLLECTION
        client = get_milvus_client()

        # 集合不存在则创建（含BM25 Function）
        if not client.has_collection(collection_name=collection_name):
            create_chunks_collection(client, collection_name, lm_config.EMBEDDING_DIM)

        # 幂等性处理：删除同一file_title的旧数据
        file_title = state.get("file_title", "")
        if file_title:
            client.load_collection(collection_name=collection_name)
            safe_title = escape_milvus_string(file_title)
            client.delete(collection_name=collection_name, filter=f'file_title=="{safe_title}"')
            logger.info(f"幂等性处理完成，已删除 file_title={file_title} 的旧数据")

        # 批量插入Chunks
        inserted_count = 0
        for i in range(0, len(chunks), INSERT_BATCH_SIZE):
            batch = chunks[i:i + INSERT_BATCH_SIZE]
            data = []
            for chunk in batch:
                row = {
                    "content": chunk.get("content", ""),
                    "title": chunk.get("title", ""),
                    "parent_title": chunk.get("parent_title", ""),
                    "part": int(chunk.get("part", 0)),
                    "file_title": chunk.get("file_title", file_title),
                    "item_name": chunk.get("item_name", ""),
                    "dense_vector": chunk.get("dense_vector", []),
                }
                data.append(row)

            client.insert(collection_name=collection_name, data=data)
            inserted_count += len(data)
            logger.info(f"批次插入完成: {inserted_count}/{len(chunks)}")

        # 加载集合使数据可查
        client.load_collection(collection_name=collection_name)
        logger.info(f"入库完成，共插入 {inserted_count} 条Chunk到集合 {collection_name}")

    except Exception as e:
        logger.error(f"入库Milvus失败: {str(e)}", exc_info=True)
    finally:
        add_done_task(state["task_id"], func_name)

    return state
