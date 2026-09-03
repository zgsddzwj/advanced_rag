"""
Milvus 数据仓储（演进3）
kb_chunks / kb_item_names 两个集合的数据访问：
集合创建、幂等删除、批量插入、行查询、主题对齐检索。
检索专用的 hybrid_search（Dense+BM25+RRF）保留在 app/clients/milvus_utils.py，
属于检索策略而非数据访问，由演进7进一步策略化。
"""
from typing import Any, Dict, List, Optional

from pymilvus import MilvusClient

from app.core.logger import logger
from app.utils.escape_milvus_string_utils import escape_milvus_string

# 预览/聚合场景只取必要字段，避免全量 content 传输
_DOC_AGG_FIELDS = ["file_title", "item_name", "title"]
_CHUNK_FIELDS = ["title", "parent_title", "part", "content", "item_name", "file_title"]


class MilvusRepository:
    """Milvus 知识库集合仓储（可注入 MilvusClient 替身）"""

    def __init__(self, client: Optional[MilvusClient] = None):
        self._client = client

    @property
    def client(self) -> MilvusClient:
        if self._client is None:
            from app.clients.milvus_utils import get_milvus_client
            self._client = get_milvus_client()
        return self._client

    # ---------- 集合管理 ----------

    def has_collection(self, collection_name: str) -> bool:
        return self.client.has_collection(collection_name=collection_name)

    def ensure_chunks_collection(self, vector_dimension: int) -> str:
        """确保 kb_chunks 集合存在（不存在则创建，含 BM25 Function）"""
        name = _settings().chunks_collection
        if not self.client.has_collection(collection_name=name):
            from app.clients.milvus_utils import create_chunks_collection
            create_chunks_collection(self.client, name, vector_dimension)
        return name

    def ensure_item_names_collection(self, vector_dimension: int) -> str:
        """确保 kb_item_names 集合存在"""
        name = _settings().item_names_collection
        if not self.client.has_collection(collection_name=name):
            from app.clients.milvus_utils import create_item_names_collection
            create_item_names_collection(self.client, name, vector_dimension)
        return name

    def _load(self, collection_name: str):
        from app.clients.milvus_utils import ensure_collection_loaded
        ensure_collection_loaded(self.client, collection_name)

    # ---------- kb_chunks ----------

    def delete_by_file_title(self, file_title: str) -> bool:
        """删除指定 file_title 的全部 chunks；集合不存在时返回 False"""
        name = _settings().chunks_collection
        if not self.client.has_collection(collection_name=name):
            logger.warning(f"集合 {name} 不存在，跳过删除")
            return False
        self._load(name)
        self.client.delete(collection_name=name, filter=f'file_title=="{escape_milvus_string(file_title)}"')
        logger.info(f"已从 {name} 删除 file_title={file_title} 的 chunks")
        return True

    def insert_chunks(self, chunks: List[Dict[str, Any]], file_title: str, batch_size: int = 50) -> int:
        """批量插入 chunks，返回插入总数"""
        name = _settings().chunks_collection
        inserted = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            data = [
                {
                    "content": chunk.get("content", ""),
                    "title": chunk.get("title", ""),
                    "parent_title": chunk.get("parent_title", ""),
                    "part": int(chunk.get("part", 0)),
                    "file_title": chunk.get("file_title", file_title),
                    "item_name": chunk.get("item_name", ""),
                    "dense_vector": chunk.get("dense_vector", []),
                }
                for chunk in batch
            ]
            self.client.insert(collection_name=name, data=data)
            inserted += len(data)
            logger.info(f"批次插入完成: {inserted}/{len(chunks)}")
        return inserted

    def list_document_agg_rows(self) -> List[Dict[str, Any]]:
        """查询文档聚合所需字段行（file_title/item_name/title）"""
        name = _settings().chunks_collection
        if not self.client.has_collection(collection_name=name):
            return []
        self._load(name)
        return self.client.query(collection_name=name, filter="", output_fields=_DOC_AGG_FIELDS, limit=16384)

    def get_chunks(self, file_title: str, limit: int = 500) -> List[Dict[str, Any]]:
        """按 file_title 查询全部 chunks（按 part 升序）"""
        name = _settings().chunks_collection
        if not self.client.has_collection(collection_name=name):
            return []
        self._load(name)
        chunks = self.client.query(
            collection_name=name,
            filter=f'file_title=="{escape_milvus_string(file_title)}"',
            output_fields=_CHUNK_FIELDS,
            limit=limit,
        )
        chunks.sort(key=lambda x: x.get("part", 0))
        return chunks

    def has_chunks(self, file_title: str) -> bool:
        """判断指定文档在 Milvus 中是否有 chunks"""
        name = _settings().chunks_collection
        if not self.client.has_collection(collection_name=name):
            return False
        self._load(name)
        results = self.client.query(
            collection_name=name,
            filter=f'file_title=="{escape_milvus_string(file_title)}"',
            output_fields=["file_title"],
            limit=1,
        )
        return bool(results)

    # ---------- kb_item_names ----------

    def delete_item_names_by_file_title(self, file_title: str) -> bool:
        """删除指定 file_title 的主题记录；集合不存在时返回 False"""
        name = _settings().item_names_collection
        if not self.client.has_collection(collection_name=name):
            logger.warning(f"集合 {name} 不存在，跳过删除")
            return False
        self._load(name)
        self.client.delete(collection_name=name, filter=f'file_title=="{escape_milvus_string(file_title)}"')
        logger.info(f"已从 {name} 删除 file_title={file_title} 的记录")
        return True

    def replace_item_name(self, file_title: str, item_name: str, dense_vector: List[float]):
        """幂等写入文档主题：删除同名记录后插入（含稠密向量）"""
        name = _settings().item_names_collection
        self._load(name)
        if item_name:
            self.client.delete(collection_name=name, filter=f'item_name=="{escape_milvus_string(item_name)}"')
        data: Dict[str, Any] = {"file_title": file_title, "item_name": item_name}
        if dense_vector:
            data["dense_vector"] = dense_vector
        self.client.insert(collection_name=name, data=[data])
        self._load(name)

    def search_top_item_name(self, dense_vector: List[float], limit: int = 1) -> List[Dict[str, Any]]:
        """主题向量对齐：按稠密向量检索最匹配的文档主题，返回 hits 列表"""
        name = _settings().item_names_collection
        self._load(name)
        return self.client.search(
            collection_name=name,
            data=[dense_vector],
            anns_field="dense_vector",
            limit=limit,
            output_fields=["item_name", "file_title"],
        )


def _settings():
    """延迟读取统一配置（便于测试注入）"""
    from app.conf.settings import settings
    return settings


_repository: Optional[MilvusRepository] = None


def get_milvus_repository() -> MilvusRepository:
    """获取 Milvus 仓储单例"""
    global _repository
    if _repository is None:
        _repository = MilvusRepository()
    return _repository
