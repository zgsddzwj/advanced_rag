"""
HyDE 假设性文档检索节点（节点3）
1. LLM 生成假设性回答
2. 向量化假设性回答
3. Dense + BM25 混合检索
4. 判断是否需要网络搜索
"""
import sys
from typing import List, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.core.load_prompt import load_prompt
from app.lm.lm_utils import get_llm_client
from app.lm.embedding_utils import generate_embedding
from app.clients.milvus_utils import (
    get_milvus_client,
    create_hybrid_search_requests,
    hybrid_search,
)
from app.conf.milvus_config import milvus_config
from app.utils.escape_milvus_string_utils import escape_milvus_string
from app.utils.task_utils import add_running_task, add_done_task

# HyDE 检索参数
HYDE_SEARCH_LIMIT = 15
HYDE_OUTPUT_LIMIT = 10
# 判断需要网络搜索的阈值：总结果数低于此值则触发网络搜索
MIN_RESULTS_THRESHOLD = 5
# 假设性回答最大长度
HYDE_TEXT_MAX_LEN = 500


def node_search_embedding_hyde(state: QueryGraphState) -> QueryGraphState:
    """HyDE 假设性文档检索节点"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)

    try:
        query = state.get("rewritten_query") or state.get("query", "")
        if not query:
            logger.warning("查询文本为空，跳过 HyDE 检索")
            state["hyde_chunks"] = []
            state["need_web_search"] = True
            return state

        # Step 1: LLM 生成假设性回答
        hyde_text = _generate_hyde_text(query)
        state["hyde_text"] = hyde_text
        logger.info(f"HyDE 假设性回答生成完成，长度: {len(hyde_text)}")

        collection_name = milvus_config.CHUNKS_COLLECTION
        client = get_milvus_client()

        # 集合不存在则跳过
        if not client.has_collection(collection_name=collection_name):
            logger.warning(f"集合 {collection_name} 不存在，跳过 HyDE 检索")
            state["hyde_chunks"] = []
            state["need_web_search"] = True
            return state

        client.load_collection(collection_name=collection_name)

        # Step 2: 向量化假设性回答
        dense_vector = generate_embedding(hyde_text)

        # Step 3: 构造过滤表达式
        expr = _build_filter_expr(state.get("item_names", []))

        # Step 4: 构造混合搜索请求
        reqs = create_hybrid_search_requests(
            dense_vector=dense_vector,
            query_text=hyde_text,
            expr=expr,
            limit=HYDE_SEARCH_LIMIT,
        )

        # Step 5: 执行混合检索
        results = hybrid_search(
            client=client,
            collection_name=collection_name,
            reqs=reqs,
            limit=HYDE_OUTPUT_LIMIT,
            output_fields=[
                "chunk_id", "content", "title", "parent_title",
                "part", "file_title", "item_name",
            ],
        )

        # Step 6: 规范化结果
        chunks = _normalize_results(results, source="hyde")
        state["hyde_chunks"] = chunks

        # Step 7: 判断是否需要网络搜索
        embedding_chunks = state.get("embedding_chunks", [])
        total_unique = _count_unique_chunks(embedding_chunks, chunks)
        need_web = total_unique < MIN_RESULTS_THRESHOLD
        state["need_web_search"] = need_web

        logger.info(f"HyDE 检索完成: 返回 {len(chunks)} 条结果，"
                    f"总唯一结果 {total_unique} 条，"
                    f"需要网络搜索: {need_web}")

    except Exception as e:
        logger.error(f"HyDE 检索失败: {str(e)}", exc_info=True)
        state["hyde_chunks"] = []
        state["need_web_search"] = True
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _generate_hyde_text(query: str) -> str:
    """调用 LLM 生成假设性回答"""
    try:
        prompt = load_prompt("hyde_generate", query=query)
        llm = get_llm_client()
        messages = [
            SystemMessage(content="你是一个技术文档专家，擅长生成假设性回答用于向量检索。"),
            HumanMessage(content=prompt),
        ]
        resp = llm.invoke(messages)
        text = getattr(resp, "content", "").strip()

        # 限制长度
        if len(text) > HYDE_TEXT_MAX_LEN:
            text = text[:HYDE_TEXT_MAX_LEN]

        return text

    except Exception as e:
        logger.error(f"生成 HyDE 文本失败: {e}，使用原始查询替代")
        return query


def _build_filter_expr(item_names: List[str]) -> str:
    """构造 Milvus 过滤表达式"""
    if not item_names:
        return ""

    escaped_names = [escape_milvus_string(name) for name in item_names if name]
    if not escaped_names:
        return ""

    names_str = ", ".join([f'"{n}"' for n in escaped_names])
    expr = f"item_name in [{names_str}]"
    return expr


def _normalize_results(results: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """规范化检索结果"""
    chunks = []
    if not results:
        return chunks

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


def _count_unique_chunks(
    embedding_chunks: List[Dict], hyde_chunks: List[Dict]
) -> int:
    """统计两路检索结果的唯一 chunk 数量"""
    seen_ids = set()
    for chunk in embedding_chunks + hyde_chunks:
        chunk_id = chunk.get("chunk_id", "")
        if chunk_id:
            seen_ids.add(chunk_id)
        else:
            # 无 chunk_id 则用 content 前缀去重
            content = chunk.get("content", "")[:100]
            seen_ids.add(content)
    return len(seen_ids)
