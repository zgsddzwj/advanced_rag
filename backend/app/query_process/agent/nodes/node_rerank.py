"""
Rerank 重排节点（节点6）
调用 gte-rerank API 对 RRF 融合结果进行精准重排序
"""
import sys
from typing import List, Dict, Any

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.lm.rerank_utils import rerank_documents
from app.utils.task_utils import add_running_task, add_done_task

# Rerank 返回 Top N
RERANK_TOP_N = 8
# 最低分数阈值：低于此分数的结果将被过滤
RERANK_MIN_SCORE = 0.02
# 上下文最大切片数
MAX_CONTEXT_CHUNKS = 10


def node_rerank(state: QueryGraphState) -> QueryGraphState:
    """Rerank 重排节点"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)

    try:
        rrf_chunks = state.get("rrf_chunks", [])
        query = state.get("rewritten_query") or state.get("query", "")

        if not rrf_chunks:
            logger.warning("RRF 结果为空，跳过 Rerank")
            state["reranked_docs"] = []
            return state

        if not query:
            logger.warning("查询文本为空，跳过 Rerank")
            state["reranked_docs"] = rrf_chunks[:RERANK_TOP_N]
            return state

        # 截取前 N 条进行 Rerank（API 有数量限制）
        candidates = rrf_chunks[:MAX_CONTEXT_CHUNKS]
        logger.info(f"Rerank 候选: {len(candidates)} 条，query: {query[:50]}...")

        # 调用 gte-rerank API
        reranked = rerank_documents(
            query=query,
            documents=candidates,
            text_field="content",
            top_n=RERANK_TOP_N,
        )

        # 动态截断：过滤低分结果
        filtered = _dynamic_truncate(reranked)

        state["reranked_docs"] = filtered
        logger.info(f"Rerank 完成: 返回 {len(filtered)} 条结果")
        if filtered:
            logger.info(f"Top1 rerank score: {filtered[0].get('score', 0):.4f}")

    except Exception as e:
        logger.error(f"Rerank 失败: {str(e)}", exc_info=True)
        # 失败时回退到 RRF 结果
        state["reranked_docs"] = state.get("rrf_chunks", [])[:RERANK_TOP_N]
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _dynamic_truncate(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """动态截断：过滤低分结果"""
    if not docs:
        return []

    filtered = []
    for doc in docs:
        score = doc.get("score", 0.0)
        if score >= RERANK_MIN_SCORE:
            filtered.append(doc)
        else:
            logger.debug(f"Rerank 截断: score={score:.4f} < {RERANK_MIN_SCORE}")

    # 至少保留 1 条结果
    if not filtered and docs:
        filtered = [docs[0]]

    return filtered
