"""
网络搜索节点（节点4）
调用百炼 MCP 进行联网搜索，获取互联网实时信息
"""
import sys
from typing import List, Dict, Any

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.lm.web_search_utils import web_search
from app.utils.task_utils import add_running_task, add_done_task

# 网络搜索返回结果数量
WEB_SEARCH_COUNT = 5


def node_web_search_mcp(state: QueryGraphState) -> QueryGraphState:
    """网络搜索节点：调用百炼 MCP 联网搜索"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)

    try:
        query = state.get("rewritten_query") or state.get("query", "")
        if not query:
            logger.warning("查询文本为空，跳过网络搜索")
            state["web_search_docs"] = []
            return state

        # 调用百炼 MCP 网络搜索
        docs = web_search(query, count=WEB_SEARCH_COUNT)

        # 规范化结果格式，与向量检索结果统一
        normalized_docs = _normalize_web_results(docs)
        state["web_search_docs"] = normalized_docs

        logger.info(f"网络搜索完成: 返回 {len(normalized_docs)} 条结果")

    except Exception as e:
        logger.error(f"网络搜索失败: {str(e)}", exc_info=True)
        state["web_search_docs"] = []
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _normalize_web_results(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将网络搜索结果规范化为统一格式"""
    normalized = []
    for idx, doc in enumerate(docs):
        item = {
            "chunk_id": f"web_{idx}",
            "content": doc.get("content", ""),
            "title": doc.get("title", ""),
            "parent_title": "",
            "part": 0,
            "file_title": doc.get("title", ""),
            "item_name": "",
            "url": doc.get("url", ""),
            "score": 0.0,
            "source": "web",
        }
        normalized.append(item)

    return normalized
