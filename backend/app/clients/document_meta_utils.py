"""
文档元数据管理工具
在 MongoDB 中维护文档的元数据（file_title, content_hash, status），
用于判断文档是新增还是变更，支持 Kafka 事件驱动同步。
"""
import hashlib
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.clients.mongo_history_utils import get_history_mongo_tool
from app.core.logger import logger

# 元数据集合名
META_COLLECTION = "document_meta"


def _get_collection():
    """获取 document_meta 集合"""
    return get_history_mongo_tool().db[META_COLLECTION]


def compute_content_hash(file_path: str) -> str:
    """计算文件内容的 MD5 哈希（hashlib.file_digest 内部按大块读取，减少大文件的 IO 次数）"""
    try:
        with open(file_path, "rb") as f:
            return hashlib.file_digest(f, "md5").hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败: {file_path}, {e}")
        return ""


def upsert_metadata(
    file_title: str,
    content_hash: str,
    chunk_count: int = 0,
    item_name: str = "",
    file_path: str = "",
) -> Dict[str, Any]:
    """插入或更新文档元数据，返回旧元数据（用于判断 ADD/UPDATE）"""
    try:
        coll = _get_collection()
        now = datetime.now(timezone.utc)

        # 查询旧记录
        old_doc = coll.find_one({"file_title": file_title})

        # upsert
        coll.update_one(
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


def get_metadata(file_title: str) -> Optional[Dict[str, Any]]:
    """查询文档元数据"""
    try:
        coll = _get_collection()
        return coll.find_one({"file_title": file_title})
    except Exception as e:
        logger.error(f"查询文档元数据失败: {e}")
        return None


def delete_metadata(file_title: str) -> bool:
    """删除文档元数据"""
    try:
        coll = _get_collection()
        result = coll.delete_one({"file_title": file_title})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"删除文档元数据失败: {e}")
        return False


def mark_status(file_title: str, status: str):
    """更新文档状态 (active / syncing / deleted)"""
    try:
        coll = _get_collection()
        coll.update_one(
            {"file_title": file_title},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        logger.error(f"更新文档状态失败: {e}")


def list_all_metadata() -> list:
    """列出所有文档元数据"""
    try:
        coll = _get_collection()
        return list(coll.find({}, {"_id": 0}))
    except Exception as e:
        logger.error(f"列出文档元数据失败: {e}")
        return []
