import sys
import os
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_entry(state: ImportGraphState) -> ImportGraphState:
    """入口节点：判断文件类型，设置路由标记"""
    logger.info(f">>> 执行节点: {sys._getframe().f_code.co_name}")

    if "local_file_path" in state:
        path = state["local_file_path"]
        if path.endswith(".pdf"):
            state["is_pdf_read_enabled"] = True
        elif path.endswith(".md"):
            state["is_md_read_enabled"] = True
        # 提取 file_title
        state["file_title"] = os.path.splitext(os.path.basename(path))[0]

    return state
