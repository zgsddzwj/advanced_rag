"""向量检索节点：稠密向量+BM25混合检索"""
import sys
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


def node_search_embedding(state: QueryGraphState) -> QueryGraphState:
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    return state
