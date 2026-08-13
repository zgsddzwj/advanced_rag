"""
任务状态管理工具
基于内存字典管理任务执行进度，供前端轮询
支持 TTL 自动清理，防止内存泄漏
"""
import time
import threading
from typing import Dict, List, Any, Optional
from app.core.logger import logger

# 任务状态常量
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

# 已完成/失败任务的保留时间（秒），超时后自动清理
TASK_TTL_SECONDS = 3600  # 1 小时
# 清理检查间隔（秒）
CLEANUP_INTERVAL = 600  # 10 分钟

# 全局任务状态字典
_task_store: Dict[str, Dict[str, Any]] = {}
# 任务完成时间戳记录
_task_done_timestamp: Dict[str, float] = {}
# 清理线程锁
_cleanup_lock = threading.Lock()
_cleanup_started = False
# 任务存储读写锁（保证多线程并发安全）
_store_lock = threading.RLock()


def _start_cleanup_thread():
    """启动后台清理线程（仅启动一次）"""
    global _cleanup_started
    with _cleanup_lock:
        if _cleanup_started:
            return
        _cleanup_started = True
        thread = threading.Thread(target=_cleanup_loop, daemon=True)
        thread.start()
        logger.info("任务状态清理线程已启动")


def _cleanup_loop():
    """后台清理循环"""
    while True:
        time.sleep(CLEANUP_INTERVAL)
        try:
            _cleanup_expired_tasks()
        except Exception as e:
            logger.warning(f"任务清理异常: {e}")


def _cleanup_expired_tasks():
    """清理过期的已完成/失败任务"""
    now = time.time()
    with _store_lock:
        expired_ids = [
            task_id for task_id, done_ts in _task_done_timestamp.items()
            if now - done_ts > TASK_TTL_SECONDS
        ]
        for task_id in expired_ids:
            _task_store.pop(task_id, None)
            _task_done_timestamp.pop(task_id, None)
    if expired_ids:
        logger.info(f"清理过期任务: {len(expired_ids)} 个")


def _ensure_task(task_id: str):
    """确保任务存在于字典中"""
    with _store_lock:
        if task_id not in _task_store:
            _task_store[task_id] = {
                "status": TASK_STATUS_PENDING,
                "done_list": [],
                "running_list": [],
                "results": {}
            }


def update_task_status(task_id: str, status: str, is_stream: bool = False):
    """更新任务全局状态"""
    _ensure_task(task_id)
    with _store_lock:
        _task_store[task_id]["status"] = status
    logger.info(f"[{task_id}] 任务状态更新: {status}")

    # 记录完成时间戳，用于 TTL 清理
    if status in (TASK_STATUS_COMPLETED, TASK_STATUS_FAILED):
        with _store_lock:
            _task_done_timestamp[task_id] = time.time()


def add_running_task(task_id: str, node_name: str, is_stream: bool = False):
    """标记节点为运行中"""
    _ensure_task(task_id)
    with _store_lock:
        if node_name not in _task_store[task_id]["running_list"]:
            _task_store[task_id]["running_list"].append(node_name)
    logger.info(f"[{task_id}] 节点运行中: {node_name}")


def add_done_task(task_id: str, node_name: str, is_stream: bool = False):
    """标记节点为已完成"""
    _ensure_task(task_id)
    with _store_lock:
        if node_name in _task_store[task_id]["running_list"]:
            _task_store[task_id]["running_list"].remove(node_name)
        if node_name not in _task_store[task_id]["done_list"]:
            _task_store[task_id]["done_list"].append(node_name)
        done_list = list(_task_store[task_id]["done_list"])
        running_list = list(_task_store[task_id]["running_list"])
    logger.info(f"[{task_id}] 节点完成: {node_name}")

    # 如果是流式模式，触发 SSE 推送
    if is_stream:
        from app.utils.sse_utils import push_to_session, SSEEvent
        push_to_session(task_id, SSEEvent.PROGRESS, {
            "done_list": done_list,
            "running_list": running_list
        })


def get_task_status(task_id: str) -> str:
    """获取任务全局状态"""
    _ensure_task(task_id)
    with _store_lock:
        return _task_store[task_id]["status"]


def get_done_task_list(task_id: str) -> List[str]:
    """获取已完成节点列表"""
    _ensure_task(task_id)
    with _store_lock:
        return list(_task_store[task_id]["done_list"])


def get_running_task_list(task_id: str) -> List[str]:
    """获取运行中节点列表"""
    _ensure_task(task_id)
    with _store_lock:
        return list(_task_store[task_id]["running_list"])


def set_task_result(task_id: str, key: str, value: Any):
    """存储任务结果数据"""
    _ensure_task(task_id)
    with _store_lock:
        _task_store[task_id]["results"][key] = value


def get_task_result(task_id: str, key: str, default: Any = None) -> Any:
    """获取任务结果数据"""
    _ensure_task(task_id)
    with _store_lock:
        return _task_store[task_id]["results"].get(key, default)


def get_all_task_ids() -> List[str]:
    """获取所有任务 ID 列表"""
    with _store_lock:
        return list(_task_store.keys())


# 启动自动清理线程
_start_cleanup_thread()
