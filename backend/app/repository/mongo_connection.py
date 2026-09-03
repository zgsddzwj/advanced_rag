"""
MongoDB 连接管理器（演进3）
懒加载单例：首次访问时才建立连接，并统一超时参数。
此前 mongo_history_utils 在模块导入期同步建连，基础设施未就绪时
每个导入该模块的进程都要等待完整的 serverSelectionTimeout。
"""
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

from app.conf.settings import settings
from app.core.logger import logger

_client: Optional[MongoClient] = None


def get_mongo_client() -> MongoClient:
    """获取 MongoClient 懒加载单例"""
    global _client
    if _client is None:
        _client = MongoClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=settings.mongo_server_selection_timeout_ms,
        )
        logger.info(f"MongoDB 客户端已建立: db={settings.mongo_db_name}")
    return _client


def get_mongo_db() -> Database:
    """获取数据库句柄（不触发连接，首次操作时才真正建连）"""
    return get_mongo_client()[settings.mongo_db_name]


def close_mongo():
    """关闭连接（FastAPI shutdown 时调用）"""
    global _client
    if _client is not None:
        try:
            _client.close()
            logger.info("MongoDB 连接已关闭")
        except Exception as e:
            logger.warning(f"关闭 MongoDB 连接异常: {e}")
        finally:
            _client = None
