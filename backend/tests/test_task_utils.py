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

    def test_read_unknown_task_creates_nothing(self):
        """轮询不存在的 task_id 不再创建条目（读路径零创建，防内存泄漏）"""
        assert task_utils.get_task_status("ghost") == task_utils.TASK_STATUS_PENDING
        assert task_utils.get_done_task_list("ghost") == []
        assert task_utils.get_running_task_list("ghost") == []
        assert "ghost" not in task_utils._task_store

    def test_stuck_task_cleaned_up(self, monkeypatch):
        """超时仍未终结的僵死任务被兜底清理，新任务不受影响"""
        task_utils.add_running_task("zombie", "node_a")
        # 把僵尸任务的创建时间拨回 7 小时前
        task_utils._task_store["zombie"]["created_at"] = (
            __import__("time").time() - task_utils.STUCK_TASK_TTL_SECONDS - 3600
        )
        task_utils.add_running_task("fresh", "node_a")

        task_utils._cleanup_expired_tasks()

        assert "zombie" not in task_utils._task_store
        assert "fresh" in task_utils._task_store

    def test_terminal_task_ttl_cleanup_still_works(self):
        """终态任务按原有 TTL 清理，行为不变"""
        task_utils.update_task_status("done1", task_utils.TASK_STATUS_COMPLETED)
        task_utils._task_done_timestamp["done1"] = (
            __import__("time").time() - task_utils.TASK_TTL_SECONDS - 10
        )
        task_utils._cleanup_expired_tasks()
        assert "done1" not in task_utils._task_store
