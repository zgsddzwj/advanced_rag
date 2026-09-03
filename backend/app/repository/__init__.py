"""
数据访问层（Repository 模式，演进3）
================================================
将 MongoDB / Milvus 的原始数据访问从业务节点与 API 服务中剥离：

- 业务层只面向仓储接口（save/get/delete/search），不再拼接 pymongo/pymilvus 调用
- 仓储实现可注入替身（fake/mongo mock），业务逻辑可脱离基础设施单测
- Mongo 连接懒加载：首次真实访问时才建立连接，消除模块导入期的连接等待
"""
from app.repository.mongo_connection import get_mongo_db, close_mongo
from app.repository.chat_history_repository import (
    ChatHistoryRepository,
    get_chat_history_repository,
)
from app.repository.document_meta_repository import (
    DocumentMetaRepository,
    get_document_meta_repository,
)
from app.repository.milvus_repository import (
    MilvusRepository,
    get_milvus_repository,
)

__all__ = [
    "get_mongo_db",
    "close_mongo",
    "ChatHistoryRepository",
    "get_chat_history_repository",
    "DocumentMetaRepository",
    "get_document_meta_repository",
    "MilvusRepository",
    "get_milvus_repository",
]
