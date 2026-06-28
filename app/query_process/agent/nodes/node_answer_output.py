"""回答输出节点：LLM基于检索结果生成最终回答，支持SSE流式输出"""
import sys
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


def node_answer_output(state: QueryGraphState) -> QueryGraphState:
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    return state
