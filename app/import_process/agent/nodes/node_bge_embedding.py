import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_bge_embedding(state: ImportGraphState) -> ImportGraphState:
    """向量化：调用text-embedding-v3 API批量生成稠密向量"""
    logger.info(f">>> 执行节点: {sys._getframe().f_code.co_name}")
    return state
