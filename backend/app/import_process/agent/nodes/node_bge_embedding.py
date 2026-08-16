"""
向量化节点
调用 text-embedding-v3 API 批量生成稠密向量
稀疏向量由 Milvus BM25 Function 自动处理
"""
import sys
from typing import List

from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.lm.embedding_utils import generate_embeddings
from app.core.logger import logger

# 批量大小：DashScope text-embedding-v3 单次调用上限为 10
BATCH_SIZE = 10


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
        texts = [chunk.get("content", "") for chunk in chunks]

        logger.info(f"开始向量化，共 {len(texts)} 条文本，批量大小: {BATCH_SIZE}")

        # 分批生成向量，单批失败时跳过该批次（避免零向量噪声）
        all_vectors = []
        total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
        failed_batches = 0
        # 记录每个 chunk 的向量是否有效
        valid_flags = []

        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            logger.info(f"处理批次 {batch_num}/{total_batches}，本批 {len(batch)} 条")

            try:
                vectors = generate_embeddings(batch)
                all_vectors.extend(vectors)
                valid_flags.extend([True] * len(batch))
            except Exception as e:
                logger.error(f"批次 {batch_num} 向量化失败，跳过该批次: {e}")
                # 用 None 占位，后续入库时过滤
                all_vectors.extend([None] * len(batch))
                valid_flags.extend([False] * len(batch))
                failed_batches += 1

        if failed_batches > 0:
            logger.warning(f"向量化完成（含 {failed_batches}/{total_batches} 个失败批次跳过）")

        # 将向量回填到 Chunk，过滤掉无效向量
        valid_chunks = []
        for idx, chunk in enumerate(chunks):
            if idx < len(all_vectors) and all_vectors[idx] is not None:
                chunk["dense_vector"] = all_vectors[idx]
                valid_chunks.append(chunk)
            else:
                logger.warning(f"Chunk {idx} 向量为空，已跳过")

        state["chunks"] = valid_chunks
        state["embeddings_content"] = [v for v in all_vectors if v is not None]
        logger.info(f"向量化完成，有效向量 {len(state['embeddings_content'])} 个，跳过 {failed_batches * BATCH_SIZE} 条")

    except Exception as e:
        logger.error(f"向量化失败: {str(e)}", exc_info=True)
    finally:
        add_done_task(state["task_id"], func_name)

    return state
