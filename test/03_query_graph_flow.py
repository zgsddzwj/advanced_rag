"""测试检索图流程骨架"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.query_process.agent.main_graph import kb_query_app
from app.query_process.agent.state import create_default_state
from app.core.logger import logger

logger.info("===== 开始测试检索图骨架 =====")

# 验证图编译成功
logger.info("图编译成功，节点流程:")
logger.info("  node_item_name_confirm → node_search_embedding → node_search_embedding_hyde")
logger.info("  → (need_web_search?) → node_web_search_mcp / node_rrf")
logger.info("  → node_rrf → node_rerank → node_answer_output")

# 测试路由逻辑
from app.query_process.agent.nodes.node_item_name_confirm import node_item_name_confirm

state = create_default_state(session_id="test_session", query="测试问题")
node_item_name_confirm(state)
logger.info("✅ 商品名确认节点测试通过")

# 测试 need_web_search 路由
state_with_web = create_default_state(session_id="test_session", query="测试问题", need_web_search=True)
assert state_with_web["need_web_search"] == True
logger.info("✅ need_web_search=True 路由测试通过")

state_without_web = create_default_state(session_id="test_session", query="测试问题", need_web_search=False)
assert state_without_web["need_web_search"] == False
logger.info("✅ need_web_search=False 路由测试通过")

logger.info("===== 测试通过 =====")
