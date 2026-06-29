"""
VLM 客户端封装（Qwen-VL-Plus via 百炼）
用于图片语义理解，生成图片文本描述
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.core.logger import logger
from app.conf.lm_config import lm_config

_vlm_client = None


def get_vlm_client() -> ChatOpenAI:
    """获取 VLM 客户端单例"""
    global _vlm_client
    if _vlm_client is None:
        _vlm_client = ChatOpenAI(
            model=lm_config.VLM_MODEL,
            api_key=lm_config.DASHSCOPE_API_KEY,
            base_url=lm_config.VLM_BASE_URL,
            temperature=0.1,
        )
        logger.info(f"VLM 客户端初始化成功: {lm_config.VLM_MODEL}")
    return _vlm_client


def describe_image(image_url: str) -> str:
    """
    调用 VLM 对图片进行语义描述
    :param image_url: 图片 URL（MinIO URL 或本地路径）
    :return: 图片的文本描述
    """
    vlm = get_vlm_client()

    message = HumanMessage(content=[
        {"type": "text", "text": "请详细描述这张图片的内容，包括设备名称、外观、结构、按钮位置等关键信息。用一句话概括。"},
        {"type": "image_url", "image_url": {"url": image_url}},
    ])

    response = vlm.invoke([message])
    logger.info(f"VLM 图片描述完成: {response.content[:50]}...")
    return response.content
