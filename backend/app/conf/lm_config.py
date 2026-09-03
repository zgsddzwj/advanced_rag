"""
[兼容层] AI 模型配置
演进1 后所有配置统一由 app.conf.settings 提供，本模块仅为历史引用保留。
新代码请使用：from app.conf.settings import settings
"""
from app.conf.settings import settings


class LMConfig:
    """AI 模型配置（属性委托至统一配置，只读快照）"""

    DASHSCOPE_API_KEY = settings.dashscope_api_key

    LLM_MODEL = settings.llm_model_name
    LLM_BASE_URL = settings.llm_base_url

    VLM_MODEL = settings.vlm_model_name
    VLM_BASE_URL = settings.vlm_base_url

    EMBEDDING_MODEL = settings.embedding_model_name
    EMBEDDING_DIM = settings.embedding_dimension
    EMBEDDING_BASE_URL = settings.embedding_base_url

    RERANK_MODEL = settings.rerank_model_name


lm_config = LMConfig()
