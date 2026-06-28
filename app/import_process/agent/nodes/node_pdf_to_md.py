import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_pdf_to_md(state: ImportGraphState) -> ImportGraphState:
    """PDF转Markdown：调用 MinerU 解析 PDF"""
    logger.info(f">>> 执行节点: {sys._getframe().f_code.co_name}")
    return state
