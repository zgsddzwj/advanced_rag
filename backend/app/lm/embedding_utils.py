"""
Embedding 客户端封装（text-embedding-v3 via 百炼）
仅生成稠密向量，稀疏向量由 Milvus BM25 自动处理
演进8：文本→向量结果带 TTL 缓存，重复查询/主题对齐不再重复调用 API
"""
from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
from app.core.logger import logger
from app.core.app_caches import embedding_cache
from app.utils.retry_utils import with_retry
from app.conf.settings import settings

_embedding_client: Optional[OpenAIEmbeddings] = None


def get_embedding_client() -> OpenAIEmbeddings:
    """获取 Embedding 客户端单例"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAIEmbeddings(
            model=settings.embedding_model_name,
            api_key=settings.dashscope_api_key,
            base_url=settings.embedding_base_url,
            dimensions=settings.embedding_dimension,
            check_embedding_ctx_length=False,
        )
        logger.info(f"Embedding 客户端初始化成功: {settings.embedding_model_name}")
    return _embedding_client


# DashScope text-embedding-v3 单次批量上限
EMBEDDING_BATCH_SIZE = 10


@with_retry(max_retries=2, base_delay=1.0)
def _embed_documents_uncached(texts: List[str]) -> List[List[float]]:
    """实际调用 API 的批量向量化（自动分批）"""
    client = get_embedding_client()
    all_vectors = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        batch_vectors = client.embed_documents(batch)
        all_vectors.extend(batch_vectors)
    return all_vectors


@with_retry(max_retries=2, base_delay=1.0)
def _embed_query_uncached(text: str) -> List[float]:
    """实际调用 API 的单条向量化"""
    client = get_embedding_client()
    return client.embed_query(text)


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    批量生成稠密向量：命中缓存的文本直接复用，仅未命中的走 API
    :param texts: 文本列表
    :return: 向量列表（顺序与输入一致）
    """
    results: List[Optional[List[float]]] = [None] * len(texts)
    missing_idx: List[int] = []
    for idx, text in enumerate(texts):
        cached = embedding_cache.get(text)
        if cached is not None:
            results[idx] = cached
        else:
            missing_idx.append(idx)

    if missing_idx:
        for start in range(0, len(missing_idx), EMBEDDING_BATCH_SIZE):
            batch_idx = missing_idx[start:start + EMBEDDING_BATCH_SIZE]
            batch_vectors = _embed_documents_uncached([texts[i] for i in batch_idx])
            for idx, vector in zip(batch_idx, batch_vectors):
                results[idx] = vector
                embedding_cache.set(texts[idx], vector)

    logger.info(f"Embedding 生成完成: {len(texts)} 条文本 "
                f"({len(texts) - len(missing_idx)} 条缓存命中, {len(missing_idx)} 条调用 API)")
    return results


def generate_embedding(text: str) -> List[float]:
    """
    单条文本向量化（用于查询向量化，带缓存）
    :param text: 查询文本
    :return: 稠密向量
    """
    return embedding_cache.get_or_set(text, lambda: _embed_query_uncached(text))
