"""
Milvus 字符串转义工具
用于构造 filter 表达式时安全处理字符串
"""


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
