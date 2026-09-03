"""
查询服务（演进4）
智能问答用例编排：SSE 队列管理、后台线程执行 LangGraph 检索图、对话历史
"""
import threading
import uuid

from app.core.logger import logger
from app.utils.sse_utils import create_sse_queue, push_to_session, SSEEvent
from app.utils.task_utils import (
    update_task_status,
    TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
)
from app.repository.chat_history_repository import get_chat_history_repository


class QueryService:
    """智能问答用例服务"""

    def __init__(self, history_repo=None):
        self._history_repo = history_repo

    @property
    def history_repo(self):
        if self._history_repo is None:
            self._history_repo = get_chat_history_repository()
        return self._history_repo

    # ---------- 提问 ----------

    def ask(self, query: str, session_id: str = "") -> dict:
        """
        提交查询：创建 SSE 队列并启动后台线程执行检索图
        前端通过 /query/stream/{task_id} 接收流式回答
        """
        session_id = session_id or str(uuid.uuid4())[:8]
        task_id = str(uuid.uuid4())[:8]

        # 创建 SSE 队列（在当前事件循环中）
        create_sse_queue(task_id)

        thread = threading.Thread(
            target=self.run_query,
            args=(task_id, session_id, query),
            daemon=True,
        )
        thread.start()

        return {"session_id": session_id, "task_id": task_id, "status": "processing"}

    def run_query(self, task_id: str, session_id: str, query: str):
        """后台线程执行查询流程"""
        update_task_status(task_id, TASK_STATUS_PROCESSING)

        try:
            from app.query_process.agent.main_graph import kb_query_app
            from app.query_process.agent.state import create_default_state

            initial_state = create_default_state(
                task_id=task_id,
                session_id=session_id,
                query=query,
                is_stream=True,
            )

            logger.info(f"查询流程启动: task_id={task_id}, session_id={session_id}, query={query[:50]}")

            # 执行 LangGraph 查询流程
            kb_query_app.invoke(initial_state)

            update_task_status(task_id, TASK_STATUS_COMPLETED)
            logger.info(f"查询流程完成: task_id={task_id}")

        except Exception as e:
            logger.error(f"查询流程失败: task_id={task_id}，错误: {str(e)}", exc_info=True)
            update_task_status(task_id, TASK_STATUS_FAILED)
            push_to_session(task_id, SSEEvent.ERROR, {"message": str(e)})

    # ---------- 对话历史 ----------

    def get_history(self, session_id: str, limit: int = 20) -> list:
        """获取会话最近对话（裁剪为前端所需字段）"""
        messages = self.history_repo.get_recent(session_id, limit=limit)
        return [
            {
                "role": msg.get("role", ""),
                "text": msg.get("text", ""),
                "rewritten_query": msg.get("rewritten_query", ""),
                "item_names": msg.get("item_names", []),
                "image_urls": msg.get("image_urls", []),
                "ts": msg.get("ts", 0),
            }
            for msg in messages
        ]

    def clear_history(self, session_id: str) -> int:
        """清空会话历史"""
        return self.history_repo.clear(session_id)
