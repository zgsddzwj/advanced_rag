"""
文档元数据仓储（演进3）
document_meta 集合的数据访问：内容哈希比对、状态机（active/syncing/deleted）
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.logger import logger
from app.repository.mongo_connection import get_mongo_db

META_COLLECTION = "document_meta"


class DocumentMetaRepository:
    """document_meta 集合仓储"""

    def __init__(self, collection: Optional[Any] = None):
        self._collection = collection

    @property
    def collection(self):
        if self._collection is None:
            self._collection = get_mongo_db()[META_COLLECTION]
        return self._collection

    def upsert(
        self,
        file_title: str,
        content_hash: str,
        chunk_count: int = 0,
        item_name: str = "",
        file_path: str = "",
    ) -> Dict[str, Any]:
        """插入或更新元数据，返回旧记录（用于判断 ADD/UPDATE 事件类型）"""
        try:
            now = datetime.now(timezone.utc)
            old_doc = self.collection.find_one({"file_title": file_title})
            self.collection.update_one(
                {"file_title": file_title},
                {
                    "$set": {
                        "file_title": file_title,
                        "content_hash": content_hash,
                        "chunk_count": chunk_count,
                        "item_name": item_name,
                        "file_path": file_path,
                        "status": "active",
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "created_at": now,
                    },
                },
                upsert=True,
            )
            logger.info(f"文档元数据已保存: {file_title}, hash={content_hash[:12]}...")
            return old_doc or {}
        except Exception as e:
            logger.error(f"保存文档元数据失败: {e}")
            return {}

    def get(self, file_title: str) -> Optional[Dict[str, Any]]:
        """查询文档元数据"""
        try:
            return self.collection.find_one({"file_title": file_title})
        except Exception as e:
            logger.error(f"查询文档元数据失败: {e}")
            return None

    def delete(self, file_title: str) -> bool:
        """删除文档元数据"""
        try:
            result = self.collection.delete_one({"file_title": file_title})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"删除文档元数据失败: {e}")
            return False

    def mark_status(self, file_title: str, status: str):
        """更新文档状态 (active / syncing / deleted)"""
        try:
            self.collection.update_one(
                {"file_title": file_title},
                {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
            )
        except Exception as e:
            logger.error(f"更新文档状态失败: {e}")

    def mark_failed(self, file_title: str, error: str):
        """事件处理彻底失败后标记文档状态与错误信息（死信配套，演进6）"""
        try:
            self.collection.update_one(
                {"file_title": file_title},
                {
                    "$set": {
                        "status": "failed",
                        "last_error": error[:2000],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as e:
            logger.error(f"标记文档失败状态异常: {e}")

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有文档元数据"""
        try:
            return list(self.collection.find({}, {"_id": 0}))
        except Exception as e:
            logger.error(f"列出文档元数据失败: {e}")
            return []


_repository: Optional[DocumentMetaRepository] = None


def get_document_meta_repository() -> DocumentMetaRepository:
    """获取文档元数据仓储单例"""
    global _repository
    if _repository is None:
        _repository = DocumentMetaRepository()
    return _repository
