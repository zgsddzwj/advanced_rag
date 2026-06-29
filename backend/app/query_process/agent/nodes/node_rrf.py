"""
RRF 融合节点（节点5）
对向量检索、HyDE 检索、网络搜索三路结果进行 RRF（Reciprocal Rank Fusion）融合排序
"""
import sys
from typing import List, Dict, Any

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.utils.task_utils import add_running_task, add_done_task

# RRF 参数 k：平滑因子，通常取 60
RRF_K = 60
# RRF 融合后返回的最大数量
RRF_OUTPUT_LIMIT = 15


def node_rrf(state: QueryGraphState) -> QueryGraphState:
    """RRF 融合节点：合并三路检索结果"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)

    try:
        embedding_chunks = state.get("embedding_chunks", [])
        hyde_chunks = state.get("hyde_chunks", [])
        web_search_docs = state.get("web_search_docs", [])

        logger.info(f"RRF 输入: 向量检索 {len(embedding_chunks)} 条, "
                    f"HyDE {len(hyde_chunks)} 条, 网络搜索 {len(web_search_docs)} 条")

        # RRF 融合
        fused = _rrf_fuse(embedding_chunks, hyde_chunks, web_search_docs)

        # 截取前 N 条
        fused = fused[:RRF_OUTPUT_LIMIT]
        state["rrf_chunks"] = fused

        logger.info(f"RRF 融合完成: 返回 {len(fused)} 条结果")
        if fused:
            logger.info(f"Top1 RRF score: {fused[0].get('rrf_score', 0):.6f}")

    except Exception as e:
        logger.error(f"RRF 融合失败: {str(e)}", exc_info=True)
        state["rrf_chunks"] = []
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _rrf_fuse(
    embedding_chunks: List[Dict[str, Any]],
    hyde_chunks: List[Dict[str, Any]],
    web_search_docs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    RRF 融合算法
    score(doc) = sum(1 / (k + rank_i)) for each retrieval source i
    """
    scores: Dict[str, Dict[str, Any]] = {}

    # 向量检索结果
    for rank, chunk in enumerate(embedding_chunks):
        key = _get_chunk_key(chunk)
        if key not in scores:
            scores[key] = {"chunk": chunk, "score": 0.0, "sources": set()}
        scores[key]["score"] += 1.0 / (RRF_K + rank + 1)
        scores[key]["sources"].add("embedding")

    # HyDE 检索结果
    for rank, chunk in enumerate(hyde_chunks):
        key = _get_chunk_key(chunk)
        if key not in scores:
            scores[key] = {"chunk": chunk, "score": 0.0, "sources": set()}
        scores[key]["score"] += 1.0 / (RRF_K + rank + 1)
        scores[key]["sources"].add("hyde")

    # 网络搜索结果
    for rank, chunk in enumerate(web_search_docs):
        key = _get_chunk_key(chunk)
        if key not in scores:
            scores[key] = {"chunk": chunk, "score": 0.0, "sources": set()}
        scores[key]["score"] += 1.0 / (RRF_K + rank + 1)
        scores[key]["sources"].add("web")

    # 按分数降序排序
    sorted_items = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    # 构建输出
    result = []
    for item in sorted_items:
        chunk = item["chunk"].copy()
        chunk["rrf_score"] = round(item["score"], 6)
        chunk["sources"] = list(item["sources"])
        result.append(chunk)

    return result


def _get_chunk_key(chunk: Dict[str, Any]) -> str:
    """获取 chunk 的唯一标识，用于去重"""
    chunk_id = chunk.get("chunk_id", "")
    if chunk_id:
        return str(chunk_id)
    # 无 chunk_id 则用 content 前缀
    content = chunk.get("content", "")[:200]
    return f"content_{hash(content)}"
