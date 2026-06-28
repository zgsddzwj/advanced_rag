"""
Prompt 模板加载器
从 prompts/ 目录加载 .prompt 文件，支持变量替换
"""
import os
from app.core.logger import logger

# Prompt 模板目录
PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "prompts"
)


def load_prompt(name: str, **kwargs) -> str:
    """
    加载 Prompt 模板并填充变量
    :param name: 模板名称（不含 .prompt 后缀）
    :param kwargs: 要填充的变量
    :return: 填充后的 Prompt 字符串
    """
    file_path = os.path.join(PROMPT_DIR, f"{name}.prompt")
    
    if not os.path.exists(file_path):
        logger.error(f"Prompt 模板不存在: {file_path}")
        raise FileNotFoundError(f"Prompt 模板不存在: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        template = f.read()
    
    # 使用 str.format 替换变量
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Prompt 模板变量替换失败，缺少变量: {e}")
            raise
    return template
