"""
商品名确认节点（节点1）
1. 加载对话历史
2. LLM 改写查询 + 提取商品名
3. 商品名向量对齐（Milvus kb_item_names）
4. 用户消息写入 MongoDB
"""
import sys
import re
from typing import List, Dict, Any, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.core.load_prompt import load_prompt
from app.lm.lm_utils import get_llm_client
from app.lm.embedding_utils import generate_embedding
from app.clients.milvus_utils import get_milvus_client
from app.clients.mongo_history_utils import get_recent_messages, save_chat_message
from app.conf.milvus_config import milvus_config
from app.utils.task_utils import add_running_task, add_done_task

# 商品名对齐相似度阈值
ITEM_NAME_MATCH_THRESHOLD = 0.65
# 历史对话最大轮数
HISTORY_MAX_MESSAGES = 10


def node_item_name_confirm(state: QueryGraphState) -> QueryGraphState:
    """商品名确认节点：改写查询 + 商品名对齐 + 历史写入"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)

    try:
        # Step 1: 加载对话历史
        history = _load_history(state)

        # Step 2: LLM 改写查询 + 提取商品名
        rewritten_query, item_names = _rewrite_and_extract(state, history)

        # Step 3: 商品名向量对齐
        aligned_item_names = _align_item_names(item_names)

        # Step 4: 用户消息写入 MongoDB
        _save_user_message(state, rewritten_query, aligned_item_names)

        # 更新状态
        state["rewritten_query"] = rewritten_query
        state["item_names"] = aligned_item_names
        state["history"] = history

        logger.info(f"改写查询: {rewritten_query}")
        logger.info(f"对齐商品名: {aligned_item_names}")

    except Exception as e:
        logger.error(f"商品名确认失败: {str(e)}", exc_info=True)
        state["rewritten_query"] = state.get("query", "")
        state["item_names"] = []
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _load_history(state: QueryGraphState) -> List[Dict[str, Any]]:
    """从 MongoDB 加载最近对话历史"""
    session_id = state.get("session_id", "")
    if not session_id:
        return []

    try:
        messages = get_recent_messages(session_id, limit=HISTORY_MAX_MESSAGES)
        logger.info(f"加载历史对话: {len(messages)} 条")
        return messages
    except Exception as e:
        logger.warning(f"加载历史对话失败: {e}")
        return []


def _format_history(history: List[Dict[str, Any]]) -> str:
    """将历史对话格式化为文本"""
    if not history:
        return "（无历史对话）"

    lines = []
    for msg in history:
        role = msg.get("role", "")
        text = msg.get("text", "")
        if role == "user":
            lines.append(f"用户：{text}")
        elif role == "assistant":
            lines.append(f"助手：{text}")
    return "\n".join(lines) if lines else "（无历史对话）"


def _rewrite_and_extract(
    state: QueryGraphState, history: List[Dict[str, Any]]
) -> Tuple[str, List[str]]:
    """调用 LLM 改写查询并提取商品名"""
    query = state.get("query", "")
    if not query:
        return "", []

    try:
        history_text = _format_history(history)
        prompt = load_prompt("item_name_confirm", history=history_text, query=query)

        llm = get_llm_client()
        messages = [
            SystemMessage(content="你是一个智能助手，负责查询改写和商品名提取。"),
            HumanMessage(content=prompt),
        ]
        resp = llm.invoke(messages)
        content = getattr(resp, "content", "").strip()

        # 解析 LLM 返回
        rewritten_query, item_names = _parse_llm_response(content, query)
        return rewritten_query, item_names

    except Exception as e:
        logger.error(f"LLM 改写查询失败: {e}")
        return query, []


def _parse_llm_response(content: str, fallback_query: str) -> Tuple[str, List[str]]:
    """解析 LLM 返回的产品名称和改写问题"""
    rewritten_query = fallback_query
    item_names = []

    try:
        # 提取产品名称
        item_match = re.search(r"产品名称[：:]\s*(.+)", content)
        if item_match:
            names_str = item_match.group(1).strip()
            # 支持逗号、顿号分隔多个商品名
            item_names = [
                name.strip()
                for name in re.split(r"[,，、；;]", names_str)
                if name.strip() and name.strip() != "无"
            ]

        # 提取改写问题
        query_match = re.search(r"改写问题[：:]\s*(.+)", content)
        if query_match:
            rewritten_query = query_match.group(1).strip()

    except Exception as e:
        logger.warning(f"解析 LLM 响应失败: {e}，使用原始查询")

    return rewritten_query, item_names


def _align_item_names(item_names: List[str]) -> List[str]:
    """商品名向量对齐：在 Milvus kb_item_names 中查找最匹配的商品名"""
    if not item_names:
        return []

    collection_name = milvus_config.ITEM_NAMES_COLLECTION
    aligned = []

    try:
        client = get_milvus_client()

        # 集合不存在则跳过对齐
        if not client.has_collection(collection_name=collection_name):
            logger.warning(f"集合 {collection_name} 不存在，跳过商品名对齐")
            return item_names

        client.load_collection(collection_name=collection_name)

        for name in item_names:
            # 生成商品名向量
            dense_vector = generate_embedding(name)

            # 在 kb_item_names 中搜索
            results = client.search(
                collection_name=collection_name,
                data=[dense_vector],
                anns_field="dense_vector",
                limit=1,
                output_fields=["item_name", "file_title"],
            )

            if results and len(results) > 0 and len(results[0]) > 0:
                top_hit = results[0][0]
                score = top_hit.get("distance", 0)
                matched_name = top_hit.get("entity", {}).get("item_name", "")

                if score >= ITEM_NAME_MATCH_THRESHOLD and matched_name:
                    logger.info(f"商品名对齐: '{name}' → '{matched_name}' (score={score:.4f})")
                    aligned.append(matched_name)
                else:
                    logger.info(f"商品名未对齐: '{name}' (最近匹配 score={score:.4f})")
                    aligned.append(name)
            else:
                aligned.append(name)

    except Exception as e:
        logger.error(f"商品名对齐失败: {e}")
        return item_names

    return aligned


def _save_user_message(
    state: QueryGraphState,
    rewritten_query: str,
    item_names: List[str],
):
    """将用户消息写入 MongoDB"""
    session_id = state.get("session_id", "")
    if not session_id:
        return

    try:
        save_chat_message(
            session_id=session_id,
            role="user",
            text=state.get("query", ""),
            rewritten_query=rewritten_query,
            item_names=item_names,
        )
    except Exception as e:
        logger.warning(f"保存用户消息到 MongoDB 失败: {e}")
