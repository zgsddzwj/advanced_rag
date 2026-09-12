"""
优化2 单元测试：日志定位改用 _getframe 栈回溯
验证修复后的调用位置（name/function/line）仍准确指向业务调用行，且 request_id 正常注入
"""
import sys

from loguru import logger as base_logger

from app.core.logger import fix_log_position


def test_log_position_points_to_caller_line():
    records = []
    test_logger = base_logger.patch(fix_log_position)
    test_logger.add(lambda m: records.append(m.record), format="{message}", level="INFO")

    def _emit():
        test_logger.info("pos-check"); return sys._getframe().f_lineno

    expected_line = _emit()

    assert len(records) == 1
    record = records[0]
    assert record["message"] == "pos-check"
    assert record["name"] == "test_logger_position.py"
    assert record["function"] == "_emit"
    assert record["line"] == expected_line  # 恰好是日志调用所在的物理行


def test_request_id_injected_outside_request_context():
    records = []
    test_logger = base_logger.patch(fix_log_position)
    test_logger.add(lambda m: records.append(m.record), format="{message}", level="INFO")

    test_logger.info("ctx-check")

    assert records[0]["extra"]["request_id"] == "-"
