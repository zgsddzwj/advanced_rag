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
# 未终结任务的兜底清理时长（秒）：导入流程可能较长（PDF 云端解析），
# 取任务 TTL 的 6 倍，避免误伤仍在执行的正常任务；超过此时长仍无终态的
# 任务视为僵死任务（如服务重启丢失执行线程），一并清理防内存泄漏
STUCK_TASK_TTL_SECONDS = TASK_TTL_SECONDS * 6

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
    """
    清理过期任务：
    - 终态任务（completed/failed）超过 TASK_TTL_SECONDS
    - 未终结任务超过 STUCK_TASK_TTL_SECONDS（僵死任务：执行线程已丢失，
      永远不会再有终态，此前会永久滞留内存）
    """
    now = time.time()
    with _store_lock:
        expired_ids = [
            task_id for task_id, done_ts in _task_done_timestamp.items()
            if now - done_ts > TASK_TTL_SECONDS
        ]
        stuck_ids = [
            task_id for task_id, task in _task_store.items()
            if task_id not in _task_done_timestamp
            and now - task.get("created_at", now) > STUCK_TASK_TTL_SECONDS
        ]
        for task_id in expired_ids + stuck_ids:
            _task_store.pop(task_id, None)
            _task_done_timestamp.pop(task_id, None)
    if expired_ids or stuck_ids:
        logger.info(f"清理过期任务: {len(expired_ids)} 个（终态）, {len(stuck_ids)} 个（僵死）")


def _ensure_task(task_id: str):
    """确保任务存在于字典中；首次写入任务时才启动清理线程（消除 import 副作用）"""
    _start_cleanup_thread()
    with _store_lock:
        if task_id not in _task_store:
            _task_store[task_id] = {
                "status": TASK_STATUS_PENDING,
                "done_list": [],
                "running_list": [],
                "created_at": time.time(),
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
    """
    获取任务全局状态
    未知任务返回 pending 且不创建条目（读路径零创建，防止轮询
    不存在的 task_id 造成内存泄漏）
    """
    with _store_lock:
        task = _task_store.get(task_id)
        return task["status"] if task else TASK_STATUS_PENDING


def get_done_task_list(task_id: str) -> List[str]:
    """获取已完成节点列表（读路径零创建）"""
    with _store_lock:
        task = _task_store.get(task_id)
        return list(task["done_list"]) if task else []


def get_running_task_list(task_id: str) -> List[str]:
    """获取运行中节点列表（读路径零创建）"""
    with _store_lock:
        task = _task_store.get(task_id)
        return list(task["running_list"]) if task else []


def get_all_task_ids() -> List[str]:
    """获取所有任务 ID 列表"""
    with _store_lock:
        return list(_task_store.keys())

# 清理线程改为首个任务写入时启动（_ensure_task 内），不再在模块导入期产生线程
