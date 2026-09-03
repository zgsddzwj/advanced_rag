"""
检索器注册表（演进7：检索管线可插拔）
================================================
将「混合检索」从查询节点中抽象为可注册的 Retriever 组件：
- 节点只面向 get_retriever(name) 编排，检索实现可替换/可扩展
- 内置 MilvusHybridRetriever（Dense + BM25 + RRF），按 source 区分
  embedding（查询向量）与 hyde（假设性回答向量）两路，行为与演进前一致
- 新检索器（如多路召回、重写检索）实现 Retriever 协议后注册即可接入
"""
from typing import Dict, List, Protocol

from app.core.logger import logger
from app.query_process.agent.search_utils import build_filter_expr, normalize_results

# 每路（Dense / BM25）召回数量：为保证 RRF 融合质量，通常大于最终 top_k
LANE_RECALL_LIMIT = 15


class Retriever(Protocol):
    """检索器协议：给定查询文本与主题过滤条件，返回规范化文档列表"""

    name: str

    def retrieve(
        self,
        query: str,
        item_names: List[str],
        top_k: int,
    ) -> List[Dict]:
        ...


class MilvusHybridRetriever:
    """Milvus Dense + BM25 混合检索器"""

    def __init__(self, name: str, source: str):
        self.name = name
        self.source = source

    def retrieve(self, query: str, item_names: List[str], top_k: int) -> List[Dict]:
        """执行混合检索；集合不存在或失败时返回空列表（由上层决定是否补充检索）"""
        from app.conf.settings import settings
        from app.clients.milvus_utils import (
            get_milvus_client, create_hybrid_search_requests, hybrid_search,
            ensure_collection_loaded,
        )
        from app.lm.embedding_utils import generate_embedding

        collection_name = settings.chunks_collection
        client = get_milvus_client()

        if not client.has_collection(collection_name=collection_name):
            logger.warning(f"集合 {collection_name} 不存在，跳过检索（{self.name}）")
            return []

        ensure_collection_loaded(client, collection_name)

        dense_vector = generate_embedding(query)

        reqs = create_hybrid_search_requests(
            dense_vector=dense_vector,
            query_text=query,
            expr=build_filter_expr(item_names),
            limit=LANE_RECALL_LIMIT,
        )

        results = hybrid_search(
            client=client,
            collection_name=collection_name,
            reqs=reqs,
            limit=top_k,
            output_fields=[
                "chunk_id", "content", "title", "parent_title",
                "part", "file_title", "item_name",
            ],
        )

        return normalize_results(results, source=self.source)


# ============================================================
#  注册表
# ============================================================

_RETRIEVERS: Dict[str, Retriever] = {}


def register_retriever(retriever: Retriever) -> Retriever:
    """注册检索器实例（同名覆盖）"""
    _RETRIEVERS[retriever.name] = retriever
    return retriever


def get_retriever(name: str) -> Retriever:
    retriever = _RETRIEVERS.get(name)
    if retriever is None:
        raise KeyError(f"检索器未注册: {name}（已注册: {sorted(_RETRIEVERS)}）")
    return retriever


def registered_retrievers() -> list:
    return sorted(_RETRIEVERS.keys())


# 内置检索器：与历史两路检索一一对应
register_retriever(MilvusHybridRetriever(name="embedding", source="embedding"))
register_retriever(MilvusHybridRetriever(name="hyde", source="hyde"))
