import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_document_split(state: ImportGraphState) -> ImportGraphState:
    """文档切分：基于Markdown标题层级递归切分"""
    logger.info(f">>> 执行节点: {sys._getframe().f_code.co_name}")
    return state
