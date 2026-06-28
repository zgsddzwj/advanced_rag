"""
LLM/VLM/Embedding/Rerank 统一配置
所有 AI 模型通过阿里云百炼 API 接入
"""
import os
from dotenv import load_dotenv

load_dotenv()


class LMConfig:
    """AI 模型配置"""
    # 百炼统一 API Key
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

    # LLM (Qwen-Plus)
    LLM_MODEL = os.getenv("LLM_MODEL_NAME", "qwen-plus")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # VLM (Qwen-VL-Plus)
    VLM_MODEL = os.getenv("VLM_MODEL_NAME", "qwen-vl-plus")
    VLM_BASE_URL = os.getenv("VLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # Embedding (text-embedding-v3)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v3")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # Rerank (gte-rerank)
    RERANK_MODEL = os.getenv("RERANK_MODEL_NAME", "gte-rerank")


lm_config = LMConfig()
