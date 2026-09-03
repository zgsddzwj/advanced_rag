"""
[兼容层] Milvus 配置
演进1 后所有配置统一由 app.conf.settings 提供，本模块仅为历史引用保留。
新代码请使用：from app.conf.settings import settings
"""
from app.conf.settings import settings


class MilvusConfig:
    MILVUS_URL = settings.milvus_url
    CHUNKS_COLLECTION = settings.chunks_collection
    ITEM_NAMES_COLLECTION = settings.item_names_collection


milvus_config = MilvusConfig()
