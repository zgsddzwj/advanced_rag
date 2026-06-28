import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_item_name_recognition(state: ImportGraphState) -> ImportGraphState:
    """商品名识别：调用LLM提取文档中的产品/设备名称"""
    logger.info(f">>> 执行节点: {sys._getframe().f_code.co_name}")
    return state
