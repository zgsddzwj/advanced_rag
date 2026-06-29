"""测试导入图流程骨架 - 验证图编译和路由逻辑"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.import_process.agent.main_graph import kb_import_app
from app.import_process.agent.state import create_default_state
from app.core.logger import logger

logger.info("===== 开始测试导入图骨架 =====")

# 验证图编译成功
logger.info("图编译成功，节点列表:")
logger.info(f"  入口: node_entry")
logger.info(f"  PDF流程: node_entry → node_pdf_to_md → node_md_img → node_document_split → node_item_name_recognition → node_bge_embedding → node_import_milvus")
logger.info(f"  MD流程:  node_entry → node_md_img → node_document_split → node_item_name_recognition → node_bge_embedding → node_import_milvus")

# 测试路由逻辑（不触发实际节点执行）
from app.import_process.agent.nodes.node_entry import node_entry

# 测试 PDF 路由
state_pdf = create_default_state(task_id="test_pdf", local_file_path="test.pdf")
node_entry(state_pdf)
assert state_pdf["is_pdf_read_enabled"] == True
assert state_pdf["is_md_read_enabled"] == False
assert state_pdf["file_title"] == "test"
logger.info("✅ PDF路由测试通过")

# 测试 MD 路由
state_md = create_default_state(task_id="test_md", local_file_path="test.md")
node_entry(state_md)
assert state_md["is_md_read_enabled"] == True
assert state_md["is_pdf_read_enabled"] == False
logger.info("✅ MD路由测试通过")

# 测试不支持类型
state_txt = create_default_state(task_id="test_txt", local_file_path="test.txt")
node_entry(state_txt)
assert state_txt["is_pdf_read_enabled"] == False
assert state_txt["is_md_read_enabled"] == False
logger.info("✅ 不支持类型测试通过")

logger.info("===== 测试通过 =====")
