"""
Embedding 客户端封装（text-embedding-v3 via 百炼）
仅生成稠密向量，稀疏向量由 Milvus BM25 自动处理
"""
from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
from app.core.logger import logger
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
def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    批量生成稠密向量（自动分批，每批不超过10条）
    :param texts: 文本列表
    :return: 向量列表（每个元素为 1024 维浮点列表）
    """
    client = get_embedding_client()
    all_vectors = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        batch_vectors = client.embed_documents(batch)
        all_vectors.extend(batch_vectors)
    logger.info(f"Embedding 生成完成: {len(texts)} 条文本 → {len(all_vectors)} 个向量")
    return all_vectors


@with_retry(max_retries=2, base_delay=1.0)
def generate_embedding(text: str) -> List[float]:
    """
    单条文本向量化（用于查询向量化）
    :param text: 查询文本
    :return: 稠密向量
    """
    client = get_embedding_client()
    return client.embed_query(text)
