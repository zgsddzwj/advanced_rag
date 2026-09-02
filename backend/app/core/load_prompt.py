"""
Prompt 模板加载器
从 prompts/ 目录加载 .prompt 文件，支持变量替换
"""
import os
from typing import Dict, List, Tuple
from app.core.logger import logger

# Prompt 模板目录
PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "prompts"
)

# 模板缓存：文件路径 → (mtime, size, 模板内容)
# 命中时免磁盘 IO；文件被修改（mtime/size 变化）后自动重新加载，开发调试改模板即时生效
_template_cache: Dict[str, Tuple[float, int, str]] = {}


def _read_template(file_path: str) -> str:
    """读取模板内容（带 mtime 缓存）"""
    stat = os.stat(file_path)
    cached = _template_cache.get(file_path)
    if cached is not None and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]

    with open(file_path, "r", encoding="utf-8") as f:
        template = f.read()
    _template_cache[file_path] = (stat.st_mtime, stat.st_size, template)
    return template


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

    template = _read_template(file_path)
    
    # 使用 str.format 替换变量
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Prompt 模板变量替换失败，缺少变量: {e}")
            raise
    return template


def list_prompts() -> List[str]:
    """
    列出所有可用的 Prompt 模板名称
    :return: 模板名称列表（不含 .prompt 后缀）
    """
    if not os.path.exists(PROMPT_DIR):
        return []
    return [
        f.replace(".prompt", "")
        for f in os.listdir(PROMPT_DIR)
        if f.endswith(".prompt")
    ]
