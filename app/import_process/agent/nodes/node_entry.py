import os
import sys
from os.path import splitext

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task


def node_entry(state: ImportGraphState) -> ImportGraphState:
    """
    LangGraph知识库导入工作流 - 入口节点
    核心职责：初始化参数校验 | 自动判断文件类型(PDF/MD) | 设置解析开关 | 提取业务标识
    """
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")

    add_running_task(state["task_id"], func_name)

    try:
        # 1. 核心参数提取与非空校验
        document_path = state.get("local_file_path", "")
        if not document_path:
            logger.error(f"【{func_name}】核心参数缺失：local_file_path 为空")
            return state

        # 2. 根据文件后缀判断类型，设置对应解析开关
        if document_path.endswith(".pdf"):
            logger.info(f"文件类型: PDF → 开启PDF解析流程")
            state["is_pdf_read_enabled"] = True
            state["pdf_path"] = document_path
        elif document_path.endswith(".md"):
            logger.info(f"文件类型: MD → 开启MD解析流程")
            state["is_md_read_enabled"] = True
            state["md_path"] = document_path
        else:
            logger.warning(f"不支持的文件格式: {document_path}，仅支持 .pdf/.md")

        # 3. 提取文件无后缀纯名称，作为全局业务标识
        file_name = os.path.basename(document_path)
        state["file_title"] = splitext(file_name)[0]
        logger.info(f"文件标识提取完成: file_title = {state['file_title']}")

    finally:
        add_done_task(state["task_id"], func_name)

    return state
