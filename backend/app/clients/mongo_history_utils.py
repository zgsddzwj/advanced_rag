"""
MongoDB 对话历史工具
负责多轮对话的存取管理
"""
import os
from typing import List, Dict, Any
from datetime import datetime
from pymongo import MongoClient, DESCENDING, ASCENDING
from bson import ObjectId
from dotenv import load_dotenv

from app.core.logger import logger

load_dotenv()


class HistoryMongoTool:
    """MongoDB 历史对话记录读写工具类"""

    def __init__(self):
        try:
            self.mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
            self.db_name = os.getenv("MONGO_DB_NAME", "kb002")

            self.client = MongoClient(self.mongo_url)
            self.db = self.client[self.db_name]
            self.chat_message = self.db["chat_message"]

            # 创建复合索引：session_id 升序 + ts 降序
            self.chat_message.create_index([("session_id", 1), ("ts", -1)])

            logger.info(f"MongoDB 连接成功: {self.db_name}")
        except Exception as e:
            logger.error(f"MongoDB 连接失败: {e}")
            raise


_history_mongo_tool = None

try:
    _history_mongo_tool = HistoryMongoTool()
except Exception as e:
    logger.warning(f"MongoDB 模块加载时初始化失败: {e}")


def get_history_mongo_tool() -> HistoryMongoTool:
    """获取单例实例（懒加载）"""
    global _history_mongo_tool
    if _history_mongo_tool is None:
        _history_mongo_tool = HistoryMongoTool()
    return _history_mongo_tool


def clear_history(session_id: str) -> int:
    """清空指定会话的所有历史对话"""
    mongo_tool = get_history_mongo_tool()
    try:
        result = mongo_tool.chat_message.delete_many({"session_id": session_id})
        logger.info(f"已删除 {result.deleted_count} 条消息 (session: {session_id})")
        return result.deleted_count
    except Exception as e:
        logger.error(f"清空历史对话失败 (session: {session_id}): {e}")
        return 0


def save_chat_message(
    session_id: str,
    role: str,
    text: str,
    rewritten_query: str = "",
    item_names: List[str] = None,
    image_urls: List[str] = None,
    message_id: str = None
) -> str:
    """
    写入/更新单条会话记录
    :return: 记录唯一标识
    """
    ts = datetime.now().timestamp()

    document = {
        "session_id": session_id,
        "role": role,
        "text": text,
        "rewritten_query": rewritten_query or "",
        "item_names": item_names,
        "image_urls": image_urls,
        "ts": ts
    }

    mongo_tool = get_history_mongo_tool()
    if message_id:
        mongo_tool.chat_message.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": document}
        )
        return message_id
    else:
        result = mongo_tool.chat_message.insert_one(document)
        return str(result.inserted_id)


def get_recent_messages(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    查询指定会话的最近 N 条对话记录
    结果按时间正序排列（先按 ts 降序取最近 N 条，再反转为正序）
    """
    mongo_tool = get_history_mongo_tool()
    try:
        query = {"session_id": session_id}
        # 先按 ts 降序取最近的 limit 条，再反转为时间正序
        cursor = mongo_tool.chat_message.find(query).sort("ts", DESCENDING).limit(limit)
        messages = list(cursor)
        messages.reverse()
        return messages
    except Exception as e:
        logger.error(f"获取最近消息失败 (session: {session_id}): {e}")
        return []
