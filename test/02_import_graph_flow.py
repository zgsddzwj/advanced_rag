"""测试导入图流程骨架"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.import_process.agent.main_graph import kb_import_app
from app.import_process.agent.state import create_default_state
from app.core.logger import logger

logger.info("===== 开始测试导入图骨架 =====")

# 测试 PDF 流程
initial_state = create_default_state(local_file_path="test.pdf")
logger.info("--- 测试 PDF 流程 ---")
for event in kb_import_app.stream(initial_state):
    for key, value in event.items():
        logger.info(f"节点: {key}")

# 测试 MD 流程
initial_state_md = create_default_state(local_file_path="test.md")
logger.info("--- 测试 MD 流程 ---")
for event in kb_import_app.stream(initial_state_md):
    for key, value in event.items():
        logger.info(f"节点: {key}")

logger.info("===== 测试结束 =====")
