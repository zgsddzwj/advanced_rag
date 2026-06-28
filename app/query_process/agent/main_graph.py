"""检索流程 LangGraph 主图编排"""
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START

from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState
from app.query_process.agent.nodes.node_item_name_confirm import node_item_name_confirm
from app.query_process.agent.nodes.node_search_embedding import node_search_embedding
from app.query_process.agent.nodes.node_search_embedding_hyde import node_search_embedding_hyde
from app.query_process.agent.nodes.node_web_search_mcp import node_web_search_mcp
from app.query_process.agent.nodes.node_rrf import node_rrf
from app.query_process.agent.nodes.node_rerank import node_rerank
from app.query_process.agent.nodes.node_answer_output import node_answer_output

load_dotenv()

workflow = StateGraph(QueryGraphState)

workflow.add_node("node_item_name_confirm", node_item_name_confirm)
workflow.add_node("node_search_embedding", node_search_embedding)
workflow.add_node("node_search_embedding_hyde", node_search_embedding_hyde)
workflow.add_node("node_web_search_mcp", node_web_search_mcp)
workflow.add_node("node_rrf", node_rrf)
workflow.add_node("node_rerank", node_rerank)
workflow.add_node("node_answer_output", node_answer_output)

workflow.set_entry_point("node_item_name_confirm")


def route_after_item_name(state: QueryGraphState) -> str:
    """商品名确认后路由：始终走向量检索"""
    return "node_search_embedding"


workflow.add_conditional_edges("node_item_name_confirm", route_after_item_name, {
    "node_search_embedding": "node_search_embedding"
})

workflow.add_edge("node_search_embedding", "node_search_embedding_hyde")


def route_after_hyde(state: QueryGraphState) -> str:
    """HyDE后路由：判断是否需要网络搜索"""
    if state.get("need_web_search"):
        return "node_web_search_mcp"
    return "node_rrf"


workflow.add_conditional_edges("node_search_embedding_hyde", route_after_hyde, {
    "node_web_search_mcp": "node_web_search_mcp",
    "node_rrf": "node_rrf"
})

workflow.add_edge("node_web_search_mcp", "node_rrf")
workflow.add_edge("node_rrf", "node_rerank")
workflow.add_edge("node_rerank", "node_answer_output")
workflow.add_edge("node_answer_output", END)

kb_query_app = workflow.compile()
