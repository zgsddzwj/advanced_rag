"""
向量检索节点（节点2）
对改写后的查询进行 Dense + BM25 混合检索
"""
import sys
from typing import List, Dict, Any

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.lm.embedding_utils import generate_embedding
from app.clients.milvus_utils import (
    get_milvus_client,
    create_hybrid_search_requests,
    hybrid_search,
)
from app.conf.milvus_config import milvus_config
from app.utils.escape_milvus_string_utils import escape_milvus_string
from app.utils.task_utils import add_running_task, add_done_task

# 每路检索返回数量
SEARCH_LIMIT = 15
# 最终返回数量
SEARCH_OUTPUT_LIMIT = 10


def node_search_embedding(state: QueryGraphState) -> QueryGraphState:
    """向量检索节点：Dense + BM25 混合检索"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)

    try:
        query = state.get("rewritten_query") or state.get("query", "")
        if not query:
            logger.warning("查询文本为空，跳过检索")
            state["embedding_chunks"] = []
            return state

        collection_name = milvus_config.CHUNKS_COLLECTION
        client = get_milvus_client()

        # 集合不存在则跳过
        if not client.has_collection(collection_name=collection_name):
            logger.warning(f"集合 {collection_name} 不存在，跳过检索")
            state["embedding_chunks"] = []
            return state

        # 确保集合已加载
        client.load_collection(collection_name=collection_name)

        # Step 1: 生成稠密向量
        dense_vector = generate_embedding(query)
        logger.info(f"查询向量化完成，维度: {len(dense_vector)}")

        # Step 2: 构造过滤表达式（基于商品名）
        expr = _build_filter_expr(state.get("item_names", []))

        # Step 3: 构造混合搜索请求
        reqs = create_hybrid_search_requests(
            dense_vector=dense_vector,
            query_text=query,
            expr=expr,
            limit=SEARCH_LIMIT,
        )

        # Step 4: 执行混合检索
        results = hybrid_search(
            client=client,
            collection_name=collection_name,
            reqs=reqs,
            limit=SEARCH_OUTPUT_LIMIT,
            output_fields=[
                "chunk_id", "content", "title", "parent_title",
                "part", "file_title", "item_name",
            ],
        )

        # Step 5: 规范化结果
        chunks = _normalize_results(results, source="embedding")
        state["embedding_chunks"] = chunks

        logger.info(f"向量检索完成: 返回 {len(chunks)} 条结果")

    except Exception as e:
        logger.error(f"向量检索失败: {str(e)}", exc_info=True)
        state["embedding_chunks"] = []
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _build_filter_expr(item_names: List[str]) -> str:
    """构造 Milvus 过滤表达式"""
    if not item_names:
        return ""

    escaped_names = [escape_milvus_string(name) for name in item_names if name]
    if not escaped_names:
        return ""

    # item_name in ["name1", "name2"]
    names_str = ", ".join([f'"{n}"' for n in escaped_names])
    expr = f"item_name in [{names_str}]"
    logger.info(f"过滤表达式: {expr}")
    return expr


def _normalize_results(results: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """规范化检索结果，统一格式"""
    chunks = []
    if not results:
        return chunks

    # Milvus hybrid_search 返回的是 list[list[dict]] 或 list[dict]
    # 统一处理
    result_list = results[0] if results and isinstance(results[0], list) else results

    for hit in result_list:
        entity = hit.get("entity", hit)
        chunk = {
            "chunk_id": entity.get("chunk_id", hit.get("id", "")),
            "content": entity.get("content", ""),
            "title": entity.get("title", ""),
            "parent_title": entity.get("parent_title", ""),
            "part": entity.get("part", 0),
            "file_title": entity.get("file_title", ""),
            "item_name": entity.get("item_name", ""),
            "score": hit.get("distance", 0.0),
            "source": source,
        }
        chunks.append(chunk)

    return chunks
