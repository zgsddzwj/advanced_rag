"""
Milvus 字符串转义工具
用于构造 filter 表达式时安全处理字符串
"""

__all__ = ["escape_milvus_string", "eq_filter"]


def escape_milvus_string(s: str) -> str:
    """
    转义 Milvus filter 表达式中的字符串
    防止特殊字符导致表达式解析错误
    """
    if s is None:
        return ""
    # 替换双引号和反斜杠
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s


def eq_filter(field: str, value: str) -> str:
    """
    构造字段等值过滤表达式：field=="<转义后的值>"
    统一收口，避免各调用点手写拼接遗漏转义
    """
    return f'{field}=="{escape_milvus_string(value)}"'
