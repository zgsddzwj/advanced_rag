"""
向量化节点
调用 text-embedding-v3 API 批量生成稠密向量
稀疏向量由 Milvus BM25 Function 自动处理
"""
import sys
from typing import List, Dict, Any

from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.lm.embedding_utils import generate_embeddings
from app.core.logger import logger

# 批量大小：API 单次调用上限
BATCH_SIZE = 25


def node_bge_embedding(state: ImportGraphState) -> ImportGraphState:
    """向量化节点：为所有Chunk生成稠密向量"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    add_running_task(state["task_id"], func_name)

    try:
        chunks = state.get("chunks") or []
        if not chunks:
            logger.warning("无有效切片数据，跳过向量化")
            return state

        # 提取所有Chunk的文本内容
        texts = []
        for chunk in chunks:
            content = chunk.get("content", "")
            texts.append(content)

        logger.info(f"开始向量化，共 {len(texts)} 条文本，批量大小: {BATCH_SIZE}")

        # 分批生成向量
        all_vectors = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            logger.info(f"处理批次 {i // BATCH_SIZE + 1}/{(len(texts) + BATCH_SIZE - 1) // BATCH_SIZE}，"
                        f"本批 {len(batch)} 条")
            vectors = generate_embeddings(batch)
            all_vectors.extend(vectors)

        # 将向量回填到Chunk
        for idx, chunk in enumerate(chunks):
            chunk["dense_vector"] = all_vectors[idx]

        state["chunks"] = chunks
        state["embeddings_content"] = all_vectors
        logger.info(f"向量化完成，共生成 {len(all_vectors)} 个向量")

    except Exception as e:
        logger.error(f"向量化失败: {str(e)}", exc_info=True)
    finally:
        add_done_task(state["task_id"], func_name)

    return state
