"""
LLM 客户端封装（Qwen-Plus via 百炼 OpenAI 兼容接口）
使用 langchain_openai.ChatOpenAI，单例模式
"""
from langchain_openai import ChatOpenAI
from app.core.logger import logger
from app.conf.lm_config import lm_config

_llm_client = None


def get_llm_client() -> ChatOpenAI:
    """获取 LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = ChatOpenAI(
            model=lm_config.LLM_MODEL,
            api_key=lm_config.DASHSCOPE_API_KEY,
            base_url=lm_config.LLM_BASE_URL,
            temperature=0.3,
            streaming=True,
        )
        logger.info(f"LLM 客户端初始化成功: {lm_config.LLM_MODEL}")
    return _llm_client
