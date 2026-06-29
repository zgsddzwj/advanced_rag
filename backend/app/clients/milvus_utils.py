"""
Milvus 客户端工具
负责连接管理、集合创建（含 BM25）、混合搜索
"""
from typing import List, Dict, Any, Optional
from pymilvus import (
    MilvusClient, DataType, Function, FunctionType,
    AnnSearchRequest, RRFRanker
)
from app.core.logger import logger
from app.conf.milvus_config import milvus_config

_milvus_client = None


def get_milvus_client() -> MilvusClient:
    """获取 Milvus 客户端单例"""
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = MilvusClient(uri=milvus_config.MILVUS_URL)
        logger.info(f"Milvus 客户端连接成功: {milvus_config.MILVUS_URL}")
    return _milvus_client


def create_chunks_collection(client: MilvusClient, collection_name: str, vector_dimension: int):
    """
    创建 kb_chunks 集合（含 BM25 全文检索）
    """
    schema = client.create_schema(auto_id=True, enable_dynamic_fields=True)

    # 主键
    schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
    # content 启用中文分词分析器
    schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535,
                     enable_analyzer=True, analyzer_params={"type": "chinese"})
    schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="parent_title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="part", datatype=DataType.INT8)
    schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=65535)
    # 稀疏向量（BM25 自动生成）
    schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
    # 稠密向量
    schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)

    # 定义 BM25 Function：从 content 自动生成 sparse_vector
    schema.add_function(Function(
        name="content_bm25",
        function_type=FunctionType.BM25,
        input_field_names=["content"],
        output_field_names=["sparse_vector"],
    ))

    # 索引参数
    index_params = client.prepare_index_params()
    # 稠密向量索引：HNSW + COSINE
    index_params.add_index(
        field_name="dense_vector",
        index_name="dense_vector_index",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200}
    )
    # 稀疏向量索引：SPARSE_INVERTED_INDEX + BM25
    index_params.add_index(
        field_name="sparse_vector",
        index_name="sparse_vector_index",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
        params={"inverted_index_algo": "DAAT_MAXSCORE"}
    )

    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    logger.info(f"Milvus 集合创建成功: {collection_name}，向量维度: {vector_dimension}")


def create_item_names_collection(client: MilvusClient, collection_name: str, vector_dimension: int):
    """
    创建 kb_item_names 集合（文档级索引，商品名对齐用）
    """
    schema = client.create_schema(auto_id=True, enable_dynamic_fields=True)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="dense_vector",
        index_name="dense_vector_index",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200}
    )

    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    logger.info(f"Milvus 集合创建成功: {collection_name}，向量维度: {vector_dimension}")


def create_hybrid_search_requests(
    dense_vector: List[float],
    query_text: str,
    expr: str = "",
    limit: int = 10
) -> List[AnnSearchRequest]:
    """
    构造 Milvus 混合搜索请求（Dense + BM25）
    :param dense_vector: 稠密向量（API 生成）
    :param query_text: 查询文本（Milvus BM25 自动分词）
    :param expr: 过滤表达式
    :param limit: 每路检索返回数量
    """
    # 稠密向量检索请求
    dense_req = AnnSearchRequest(
        data=[dense_vector],
        anns_field="dense_vector",
        param={"metric_type": "COSINE", "params": {"ef": 64}},
        expr=expr,
        limit=limit
    )

    # BM25 稀疏检索请求（传入查询文本，Milvus 自动分词）
    sparse_req = AnnSearchRequest(
        data=[query_text],
        anns_field="sparse_vector",
        param={"metric_type": "BM25"},
        expr=expr,
        limit=limit
    )

    return [dense_req, sparse_req]


def hybrid_search(
    client: MilvusClient,
    collection_name: str,
    reqs: List[AnnSearchRequest],
    ranker_weights: tuple = (0.8, 0.2),
    limit: int = 5,
    output_fields: List[str] = None
) -> List[List[Dict]]:
    """
    执行 Milvus 混合检索
    :param client: MilvusClient 实例
    :param collection_name: 集合名称
    :param reqs: 混合搜索请求列表
    :param ranker_weights: Dense/BM25 权重配比
    :param limit: 最终返回数量
    :param output_fields: 返回字段
    :return: 检索结果
    """
    if output_fields is None:
        output_fields = ["chunk_id", "content", "item_name", "title", "file_title"]

    result = client.hybrid_search(
        collection_name=collection_name,
        reqs=reqs,
        ranker=RRFRanker(k=60),
        limit=limit,
        output_fields=output_fields
    )

    return result
