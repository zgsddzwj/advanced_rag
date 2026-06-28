"""HyDE假设性文档检索节点：LLM生成假设性回答→向量化→检索"""
import sys
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


def node_search_embedding_hyde(state: QueryGraphState) -> QueryGraphState:
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    return state
