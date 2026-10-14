"""
改动1 单元测试：task_utils 代码卫生
- 未使用的结果存取函数已移除
- 清理线程懒启动：import 不产生线程，首个任务写入时启动且仅启动一次
"""
import threading

import pytest

from app.utils import task_utils


@pytest.fixture(autouse=True)
def _reset_state():
    task_utils._task_store.clear()
    task_utils._task_done_timestamp.clear()
    task_utils._cleanup_started = False
    yield
    task_utils._task_store.clear()
    task_utils._task_done_timestamp.clear()
    task_utils._cleanup_started = False


class TestTaskUtilsHygiene:
    def test_result_helpers_removed(self):
        """零调用方的结果存取函数已删除"""
        assert not hasattr(task_utils, "set_task_result")
        assert not hasattr(task_utils, "get_task_result")

    def test_no_cleanup_thread_on_import(self):
        """import 模块不启动清理线程（懒启动）：重置后标记位仍为 False"""
        assert task_utils._cleanup_started is False

    def test_cleanup_thread_starts_once_on_first_task(self):
        """首个任务写入触发清理线程启动，且幂等"""
        task_utils.update_task_status("t1", task_utils.TASK_STATUS_PROCESSING)
        assert task_utils._cleanup_started is True

        before = threading.active_count()
        # 后续写入不应再启动新线程
        task_utils.update_task_status("t2", task_utils.TASK_STATUS_PROCESSING)
        task_utils.update_task_status("t3", task_utils.TASK_STATUS_PROCESSING)
        assert threading.active_count() == before

    def test_status_and_lists_still_work(self):
        """核心读写行为不受清理影响"""
        task_utils.add_running_task("t1", "node_a")
        task_utils.add_done_task("t1", "node_a")
        assert task_utils.get_task_status("t1") == task_utils.TASK_STATUS_PENDING
        assert task_utils.get_done_task_list("t1") == ["node_a"]
        assert task_utils.get_running_task_list("t1") == []
