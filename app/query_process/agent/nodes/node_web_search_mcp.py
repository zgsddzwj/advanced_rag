"""网络搜索节点：调用百炼MCP进行联网搜索"""
import sys
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


def node_web_search_mcp(state: QueryGraphState) -> QueryGraphState:
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    return state
