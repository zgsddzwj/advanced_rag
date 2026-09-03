"""
LLM 客户端封装（Qwen-Plus via 百炼 OpenAI 兼容接口）
使用 langchain_openai.ChatOpenAI，单例模式
"""
from typing import Optional
from langchain_openai import ChatOpenAI
from app.core.logger import logger
from app.conf.settings import settings

_llm_client: Optional[ChatOpenAI] = None


def get_llm_client() -> ChatOpenAI:
    """获取 LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = ChatOpenAI(
            model=settings.llm_model_name,
            api_key=settings.dashscope_api_key,
            base_url=settings.llm_base_url,
            temperature=0.3,
            streaming=True,
        )
        logger.info(f"LLM 客户端初始化成功: {settings.llm_model_name}")
    return _llm_client
