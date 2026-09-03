"""
向量检索节点（节点2）
对改写后的查询通过检索器注册表执行 Dense + BM25 混合检索（演进7）
"""
import sys

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.query_process.agent.retrievers import get_retriever
from app.query_process.agent.retrieval_config import get_retrieval_config
from app.utils.task_utils import add_running_task, add_done_task
from app.utils.thinking_utils import push_thinking_start


def node_search_embedding(state: QueryGraphState) -> QueryGraphState:
    """向量检索节点：Dense + BM25 混合检索"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)
    push_thinking_start(state["task_id"], func_name, is_stream)

    try:
        query = state.get("rewritten_query") or state.get("query", "")
        if not query:
            logger.warning("查询文本为空，跳过检索")
            state["embedding_chunks"] = []
            return state

        config = get_retrieval_config(state)
        retriever = get_retriever("embedding")

        chunks = retriever.retrieve(
            query=query,
            item_names=state.get("item_names", []),
            top_k=config.top_k,
        )
        state["embedding_chunks"] = chunks

        logger.info(f"向量检索完成: 返回 {len(chunks)} 条结果")

    except Exception as e:
        logger.error(f"向量检索失败: {str(e)}", exc_info=True)
        state["embedding_chunks"] = []
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state
