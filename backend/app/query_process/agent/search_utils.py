"""
查询流程共享工具
提取向量检索和 HyDE 检索中重复的过滤表达式构造、结果规范化逻辑
"""
from typing import List, Dict, Any

from app.core.logger import logger
from app.utils.escape_milvus_string_utils import escape_milvus_string


def build_filter_expr(item_names: List[str]) -> str:
    """
    构造 Milvus 过滤表达式（基于商品名）
    :param item_names: 商品名列表
    :return: Milvus filter 表达式字符串，无商品名时返回空字符串
    """
    if not item_names:
        return ""

    escaped_names = [escape_milvus_string(name) for name in item_names if name]
    if not escaped_names:
        return ""

    names_str = ", ".join([f'"{n}"' for n in escaped_names])
    expr = f"item_name in [{names_str}]"
    logger.info(f"过滤表达式: {expr}")
    return expr


def normalize_results(results: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """
    规范化 Milvus 检索结果，统一格式
    :param results: Milvus hybrid_search 返回结果
    :param source: 结果来源标记（embedding / hyde）
    :return: 统一格式的 chunk 列表
    """
    chunks = []
    if not results:
        return chunks

    # Milvus hybrid_search 返回的是 list[list[dict]] 或 list[dict]，统一处理
    result_list = results[0] if results and isinstance(results[0], list) else results

    for hit in result_list:
        entity = hit.get("entity", hit)
        chunk = {
            "chunk_id": entity.get("chunk_id", hit.get("id", "")),
            "content": entity.get("content", ""),
            "title": entity.get("title", ""),
            "parent_title": entity.get("parent_title", ""),
            "part": entity.get("part", 0),
            "file_title": entity.get("file_title", ""),
            "item_name": entity.get("item_name", ""),
            "score": hit.get("distance", 0.0),
            "source": source,
        }
        chunks.append(chunk)

    return chunks


def format_history(history: List[Dict[str, Any]]) -> str:
    """
    将历史对话格式化为文本
    :param history: 历史消息列表
    :return: 格式化后的历史对话文本
    """
    if not history:
        return "（无历史对话）"

    lines = []
    for msg in history:
        role = msg.get("role", "")
        text = msg.get("text", "")
        if role == "user":
            lines.append(f"用户：{text}")
        elif role == "assistant":
            lines.append(f"助手：{text}")
    return "\n".join(lines) if lines else "（无历史对话）"
