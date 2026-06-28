import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_import_milvus(state: ImportGraphState) -> ImportGraphState:
    """入库Milvus：创建集合(含BM25)→批量插入chunks→写入item_names"""
    logger.info(f">>> 执行节点: {sys._getframe().f_code.co_name}")
    return state
