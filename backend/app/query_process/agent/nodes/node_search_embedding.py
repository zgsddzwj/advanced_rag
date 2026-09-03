"""
向量检索节点（节点2）
对改写后的查询进行 Dense + BM25 混合检索
"""
import sys

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.lm.embedding_utils import generate_embedding
from app.clients.milvus_utils import (
    get_milvus_client,
    create_hybrid_search_requests,
    hybrid_search,
    ensure_collection_loaded,
)
from app.query_process.agent.search_utils import build_filter_expr, normalize_results
from app.utils.task_utils import add_running_task, add_done_task
from app.utils.thinking_utils import push_thinking_start
from app.conf.settings import settings

# 每路检索返回数量
SEARCH_LIMIT = 15
# 最终返回数量
SEARCH_OUTPUT_LIMIT = 10


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

        collection_name = settings.chunks_collection
        client = get_milvus_client()

        # 集合不存在则跳过
        if not client.has_collection(collection_name=collection_name):
            logger.warning(f"集合 {collection_name} 不存在，跳过检索")
            state["embedding_chunks"] = []
            return state

        # 确保集合已加载
        ensure_collection_loaded(client, collection_name)

        # Step 1: 生成稠密向量
        dense_vector = generate_embedding(query)
        logger.info(f"查询向量化完成，维度: {len(dense_vector)}")

        # Step 2: 构造过滤表达式（基于商品名）
        expr = build_filter_expr(state.get("item_names", []))

        # Step 3: 构造混合搜索请求
        reqs = create_hybrid_search_requests(
            dense_vector=dense_vector,
            query_text=query,
            expr=expr,
            limit=SEARCH_LIMIT,
        )

        # Step 4: 执行混合检索
        results = hybrid_search(
            client=client,
            collection_name=collection_name,
            reqs=reqs,
            limit=SEARCH_OUTPUT_LIMIT,
            output_fields=[
                "chunk_id", "content", "title", "parent_title",
                "part", "file_title", "item_name",
            ],
        )

        # Step 5: 规范化结果
        chunks = normalize_results(results, source="embedding")
        state["embedding_chunks"] = chunks

        logger.info(f"向量检索完成: 返回 {len(chunks)} 条结果")

    except Exception as e:
        logger.error(f"向量检索失败: {str(e)}", exc_info=True)
        state["embedding_chunks"] = []
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state
