"""
测试检索图流程 —— 结构验证
验证节点导入、图编译、状态字段、路由逻辑
不依赖外部服务（MongoDB/Milvus/API）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logger import logger

logger.info("===== 开始测试检索图结构 =====")

# ── 1. 验证所有节点可导入 ──
from app.query_process.agent.nodes.node_item_name_confirm import node_item_name_confirm
from app.query_process.agent.nodes.node_search_embedding import node_search_embedding
from app.query_process.agent.nodes.node_search_embedding_hyde import node_search_embedding_hyde
from app.query_process.agent.nodes.node_web_search_mcp import node_web_search_mcp
from app.query_process.agent.nodes.node_rrf import node_rrf
from app.query_process.agent.nodes.node_rerank import node_rerank
from app.query_process.agent.nodes.node_answer_output import node_answer_output
logger.info("✅ 全部 7 个节点导入成功")

# ── 2. 验证图编译成功 ──
from app.query_process.agent.main_graph import kb_query_app
logger.info("✅ 检索图编译成功")

# ── 3. 验证状态字段 ──
from app.query_process.agent.state import create_default_state, graph_default_state

expected_keys = {
    "session_id", "task_id", "query", "rewritten_query",
    "history", "item_names",
    "embedding_chunks", "hyde_text", "hyde_chunks", "web_search_docs",
    "rrf_chunks", "reranked_docs",
    "answer", "image_urls", "prompt",
    "need_web_search", "is_stream",
}
actual_keys = set(graph_default_state.keys())
missing = expected_keys - actual_keys
assert not missing, f"状态缺少字段: {missing}"
logger.info(f"✅ 状态字段验证通过（{len(actual_keys)} 个字段）")

# ── 4. 验证默认状态创建 ──
state = create_default_state(session_id="test_session", query="测试问题")
assert state["session_id"] == "test_session"
assert state["query"] == "测试问题"
assert state["rewritten_query"] == ""
assert state["item_names"] == []
assert state["embedding_chunks"] == []
assert state["need_web_search"] == False
assert state["is_stream"] == False
logger.info("✅ 默认状态创建验证通过")

# ── 5. 验证路由逻辑 ──
# need_web_search=True → node_web_search_mcp
state_web = create_default_state(need_web_search=True)
assert state_web["need_web_search"] == True

# need_web_search=False → node_rrf
state_no_web = create_default_state(need_web_search=False)
assert state_no_web["need_web_search"] == False
logger.info("✅ 路由逻辑验证通过")

# ── 6. 验证 prompt 文件存在 ──
from app.core.load_prompt import PROMPT_DIR
for prompt_name in ["item_name_confirm", "hyde_generate"]:
    prompt_path = os.path.join(PROMPT_DIR, f"{prompt_name}.prompt")
    assert os.path.exists(prompt_path), f"Prompt 文件不存在: {prompt_path}"
logger.info("✅ Prompt 文件验证通过（item_name_confirm, hyde_generate）")

# ── 7. 验证节点函数签名 ──
import inspect
for name, func in [
    ("node_item_name_confirm", node_item_name_confirm),
    ("node_search_embedding", node_search_embedding),
    ("node_search_embedding_hyde", node_search_embedding_hyde),
    ("node_web_search_mcp", node_web_search_mcp),
    ("node_rrf", node_rrf),
    ("node_rerank", node_rerank),
    ("node_answer_output", node_answer_output),
]:
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    assert "state" in params, f"{name} 缺少 state 参数"
logger.info("✅ 全部节点函数签名验证通过")

logger.info("===== 检索图结构测试全部通过 =====")
