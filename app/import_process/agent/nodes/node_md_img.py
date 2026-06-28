import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_md_img(state: ImportGraphState) -> ImportGraphState:
    """Markdown图片处理：扫描图片→上传MinIO→VLM描述→替换链接"""
    logger.info(f">>> 执行节点: {sys._getframe().f_code.co_name}")
    return state
