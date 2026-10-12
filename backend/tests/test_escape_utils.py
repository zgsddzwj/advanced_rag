"""
优化3 单元测试：Milvus 等值过滤表达式统一构造
"""
from app.utils.escape_milvus_string_utils import eq_filter, escape_milvus_string


def test_eq_filter_basic():
    assert eq_filter("file_title", "报告.pdf") == 'file_title=="报告.pdf"'


def test_eq_filter_escapes_quotes_and_backslashes():
    # 双引号与反斜杠必须转义，防止表达式解析错误/注入
    assert eq_filter("file_title", 'a"b') == 'file_title=="a\\"b"'
    assert eq_filter("file_title", "a\\b") == 'file_title=="a\\\\b"'


def test_eq_filter_none_value():
    assert eq_filter("file_title", None) == 'file_title==""'


def test_escape_behavior_unchanged():
    assert escape_milvus_string(None) == ""
