"""RRF融合节点：对多路检索结果进行RRF融合排序"""
import sys
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


def node_rrf(state: QueryGraphState) -> QueryGraphState:
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    return state
