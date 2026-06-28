"""Rerank重排节点：调用gte-rerank对融合结果进行精准重排"""
import sys
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


def node_rerank(state: QueryGraphState) -> QueryGraphState:
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    return state
