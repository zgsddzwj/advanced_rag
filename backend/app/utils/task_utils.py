"""
任务状态管理工具
基于内存字典管理任务执行进度，供前端轮询
"""
from typing import Dict, List, Any
from app.core.logger import logger

# 任务状态常量
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

# 全局任务状态字典
_task_store: Dict[str, Dict[str, Any]] = {}


def _ensure_task(task_id: str):
    """确保任务存在于字典中"""
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
    _task_store[task_id]["status"] = status
    logger.info(f"[{task_id}] 任务状态更新: {status}")


def add_running_task(task_id: str, node_name: str, is_stream: bool = False):
    """标记节点为运行中"""
    _ensure_task(task_id)
    if node_name not in _task_store[task_id]["running_list"]:
        _task_store[task_id]["running_list"].append(node_name)
    logger.info(f"[{task_id}] 节点运行中: {node_name}")


def add_done_task(task_id: str, node_name: str, is_stream: bool = False):
    """标记节点为已完成"""
    _ensure_task(task_id)
    if node_name in _task_store[task_id]["running_list"]:
        _task_store[task_id]["running_list"].remove(node_name)
    if node_name not in _task_store[task_id]["done_list"]:
        _task_store[task_id]["done_list"].append(node_name)
    logger.info(f"[{task_id}] 节点完成: {node_name}")

    # 如果是流式模式，触发 SSE 推送
    if is_stream:
        from app.utils.sse_utils import push_to_session, SSEEvent
        push_to_session(task_id, SSEEvent.PROGRESS, {
            "done_list": _task_store[task_id]["done_list"],
            "running_list": _task_store[task_id]["running_list"]
        })


def get_task_status(task_id: str) -> str:
    """获取任务全局状态"""
    _ensure_task(task_id)
    return _task_store[task_id]["status"]


def get_done_task_list(task_id: str) -> List[str]:
    """获取已完成节点列表"""
    _ensure_task(task_id)
    return _task_store[task_id]["done_list"]


def get_running_task_list(task_id: str) -> List[str]:
    """获取运行中节点列表"""
    _ensure_task(task_id)
    return _task_store[task_id]["running_list"]


def set_task_result(task_id: str, key: str, value: Any):
    """存储任务结果数据"""
    _ensure_task(task_id)
    _task_store[task_id]["results"][key] = value


def get_task_result(task_id: str, key: str, default: Any = None) -> Any:
    """获取任务结果数据"""
    _ensure_task(task_id)
    return _task_store[task_id]["results"].get(key, default)
