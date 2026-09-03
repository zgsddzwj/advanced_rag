"""
HyDE 假设性文档检索节点（节点3）
1. LLM 生成假设性回答
2. 通过检索器注册表对假设性回答执行混合检索
3. 三态联网搜索决策：配置强制开/关，或按检索结果数量自动判断（演进7）
"""
import sys
from typing import List, Dict

from langchain_core.messages import SystemMessage, HumanMessage

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.core.load_prompt import load_prompt
from app.lm.lm_utils import get_llm_client
from app.query_process.agent.retrievers import get_retriever
from app.query_process.agent.retrieval_config import get_retrieval_config
from app.core.app_caches import hyde_cache
from app.utils.task_utils import add_running_task, add_done_task
from app.utils.thinking_utils import push_thinking_start

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
    push_thinking_start(state["task_id"], func_name, is_stream)

    config = get_retrieval_config(state)

    try:
        query = state.get("rewritten_query") or state.get("query", "")
        if not query:
            logger.warning("查询文本为空，跳过 HyDE 检索")
            state["hyde_chunks"] = []
            state["need_web_search"] = _decide_web_search(config, 0)
            return state

        hyde_chunks: List[Dict] = []
        if config.enable_hyde:
            # Step 1: LLM 生成假设性回答
            hyde_text = _generate_hyde_text(query)
            state["hyde_text"] = hyde_text
            logger.info(f"HyDE 假设性回答生成完成，长度: {len(hyde_text)}")

            # Step 2: 检索器执行混合检索
            retriever = get_retriever("hyde")
            hyde_chunks = retriever.retrieve(
                query=hyde_text,
                item_names=state.get("item_names", []),
                top_k=config.top_k,
            )
        else:
            logger.info("HyDE 检索已按请求配置禁用")

        state["hyde_chunks"] = hyde_chunks

        # Step 3: 联网搜索决策
        embedding_chunks = state.get("embedding_chunks", [])
        total_unique = _count_unique_chunks(embedding_chunks, hyde_chunks)
        need_web = _decide_web_search(config, total_unique)
        state["need_web_search"] = need_web

        logger.info(f"HyDE 检索完成: 返回 {len(hyde_chunks)} 条结果，"
                    f"总唯一结果 {total_unique} 条，"
                    f"需要网络搜索: {need_web}")

    except Exception as e:
        logger.error(f"HyDE 检索失败: {str(e)}", exc_info=True)
        state["hyde_chunks"] = []
        state["need_web_search"] = _decide_web_search(config, 0)
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _decide_web_search(config, total_unique: int) -> bool:
    """三态联网搜索决策：True=强制，False=禁用，None=按结果数量自动判断"""
    if config.enable_web_search is not None:
        return config.enable_web_search
    return total_unique < MIN_RESULTS_THRESHOLD


def _generate_hyde_text(query: str) -> str:
    """获取假设性回答：优先命中缓存，未命中调用 LLM（失败回退原始查询，不缓存）"""
    def _factory() -> str:
        prompt = load_prompt("hyde_generate", query=query)
        llm = get_llm_client()
        messages = [
            SystemMessage(content="你是一个技术文档专家，擅长生成假设性回答用于向量检索。"),
            HumanMessage(content=prompt),
        ]
        resp = llm.invoke(messages)
        text = getattr(resp, "content", "").strip()
        if len(text) > HYDE_TEXT_MAX_LEN:
            text = text[:HYDE_TEXT_MAX_LEN]
        return text

    try:
        return hyde_cache.get_or_set(query, _factory)
    except Exception as e:
        logger.error(f"生成 HyDE 文本失败: {e}，使用原始查询替代")
        return query


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
