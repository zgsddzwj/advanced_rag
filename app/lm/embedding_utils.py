"""
Embedding 客户端封装（text-embedding-v3 via 百炼）
仅生成稠密向量，稀疏向量由 Milvus BM25 自动处理
"""
from typing import List
from langchain_openai import OpenAIEmbeddings
from app.core.logger import logger
from app.conf.lm_config import lm_config

_embedding_client = None


def get_embedding_client() -> OpenAIEmbeddings:
    """获取 Embedding 客户端单例"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAIEmbeddings(
            model=lm_config.EMBEDDING_MODEL,
            api_key=lm_config.DASHSCOPE_API_KEY,
            base_url=lm_config.EMBEDDING_BASE_URL,
            dimensions=lm_config.EMBEDDING_DIM,
        )
        logger.info(f"Embedding 客户端初始化成功: {lm_config.EMBEDDING_MODEL}")
    return _embedding_client


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    批量生成稠密向量
    :param texts: 文本列表
    :return: 向量列表（每个元素为 1024 维浮点列表）
    """
    client = get_embedding_client()
    vectors = client.embed_documents(texts)
    logger.info(f"Embedding 生成完成: {len(texts)} 条文本 → {len(vectors)} 个向量")
    return vectors


def generate_embedding(text: str) -> List[float]:
    """
    单条文本向量化（用于查询向量化）
    :param text: 查询文本
    :return: 稠密向量
    """
    client = get_embedding_client()
    return client.embed_query(text)
