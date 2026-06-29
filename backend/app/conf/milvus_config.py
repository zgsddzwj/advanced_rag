"""Milvus 配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class MilvusConfig:
    MILVUS_URL = os.getenv("MILVUS_URL", "http://localhost:19530")
    CHUNKS_COLLECTION = os.getenv("CHUNKS_COLLECTION", "kb_chunks")
    ITEM_NAMES_COLLECTION = os.getenv("ITEM_NAMES_COLLECTION", "kb_item_names")


milvus_config = MilvusConfig()
