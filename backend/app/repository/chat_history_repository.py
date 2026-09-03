"""
对话历史仓储（演进3）
chat_message 集合的数据访问：多轮对话的写入、查询、清空
支持注入集合替身，便于业务逻辑脱离 MongoDB 单测
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING

from app.core.logger import logger
from app.repository.mongo_connection import get_mongo_db

CHAT_MESSAGE_COLLECTION = "chat_message"


class ChatHistoryRepository:
    """chat_message 集合仓储"""

    def __init__(self, collection: Optional[Any] = None):
        # 允许注入替身集合；None 时懒加载真实集合
        self._collection = collection
        self._index_ready = False

    @property
    def collection(self):
        if self._collection is None:
            self._collection = get_mongo_db()[CHAT_MESSAGE_COLLECTION]
        if not self._index_ready and self._collection is not None:
            try:
                # 复合索引：session_id 升序 + ts 降序
                self._collection.create_index([("session_id", 1), ("ts", -1)])
                self._index_ready = True
            except Exception as e:
                logger.warning(f"创建 chat_message 索引失败（后续重试）: {e}")
        return self._collection

    def save_message(
        self,
        session_id: str,
        role: str,
        text: str,
        rewritten_query: str = "",
        item_names: Optional[List[str]] = None,
        image_urls: Optional[List[str]] = None,
        message_id: Optional[str] = None,
    ) -> str:
        """写入/更新单条会话记录，返回记录唯一标识"""
        document = {
            "session_id": session_id,
            "role": role,
            "text": text,
            "rewritten_query": rewritten_query or "",
            "item_names": item_names,
            "image_urls": image_urls,
            "ts": datetime.now().timestamp(),
        }
        if message_id:
            from bson import ObjectId
            self.collection.update_one({"_id": ObjectId(message_id)}, {"$set": document})
            return message_id
        result = self.collection.insert_one(document)
        return str(result.inserted_id)

    def get_recent(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """查询指定会话最近 N 条记录，按时间正序返回"""
        try:
            cursor = (
                self.collection.find({"session_id": session_id})
                .sort("ts", DESCENDING)
                .limit(limit)
            )
            messages = list(cursor)
            messages.reverse()
            for msg in messages:
                if "_id" in msg:
                    msg["_id"] = str(msg["_id"])
            return messages
        except Exception as e:
            logger.error(f"获取最近消息失败 (session: {session_id}): {e}")
            return []

    def clear(self, session_id: str) -> int:
        """清空指定会话的全部记录，返回删除数量"""
        try:
            result = self.collection.delete_many({"session_id": session_id})
            logger.info(f"已删除 {result.deleted_count} 条消息 (session: {session_id})")
            return result.deleted_count
        except Exception as e:
            logger.error(f"清空历史对话失败 (session: {session_id}): {e}")
            return 0

    def count(self, session_id: str) -> int:
        """统计指定会话的消息总数"""
        try:
            return self.collection.count_documents({"session_id": session_id})
        except Exception as e:
            logger.error(f"获取消息数量失败 (session: {session_id}): {e}")
            return 0


_repository: Optional[ChatHistoryRepository] = None


def get_chat_history_repository() -> ChatHistoryRepository:
    """获取对话历史仓储单例"""
    global _repository
    if _repository is None:
        _repository = ChatHistoryRepository()
    return _repository
