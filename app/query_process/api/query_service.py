"""
查询服务 FastAPI 路由
提供智能问答的 REST API，支持 SSE 流式输出
"""
import uuid
import threading
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from app.core.logger import logger
from app.utils.sse_utils import create_sse_queue, sse_generator, push_to_session, SSEEvent
from app.utils.task_utils import update_task_status, get_task_status, TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED
from app.query_process.agent.main_graph import kb_query_app
from app.query_process.agent.state import create_default_state
from app.clients.mongo_history_utils import get_recent_messages, clear_history

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    """查询请求"""
    query: str
    session_id: str = ""


@router.get("/", response_class=HTMLResponse)
async def chat_page():
    """聊天页面"""
    html_path = Path(__file__).parent.parent / "page" / "chat.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>chat.html not found</h1>")


@router.post("/ask")
async def ask(req: QueryRequest):
    """
    提交查询，返回 session_id 和 task_id
    前端通过 /query/stream/{task_id} 接收 SSE 流式回答
    """
    session_id = req.session_id or str(uuid.uuid4())[:8]
    task_id = str(uuid.uuid4())[:8]

    # 创建 SSE 队列（在当前事件循环中）
    create_sse_queue(task_id)

    # 后台线程执行查询流程
    thread = threading.Thread(
        target=_run_query,
        args=(task_id, session_id, req.query),
        daemon=True,
    )
    thread.start()

    return {"session_id": session_id, "task_id": task_id, "status": "processing"}


@router.get("/stream/{task_id}")
async def stream(task_id: str, request: Request):
    """SSE 流式输出"""
    return StreamingResponse(
        sse_generator(task_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """获取对话历史"""
    messages = get_recent_messages(session_id, limit=20)
    result = []
    for msg in messages:
        result.append({
            "role": msg.get("role", ""),
            "text": msg.get("text", ""),
            "rewritten_query": msg.get("rewritten_query", ""),
            "item_names": msg.get("item_names", []),
            "image_urls": msg.get("image_urls", []),
            "ts": msg.get("ts", 0),
        })
    return {"session_id": session_id, "messages": result}


@router.delete("/history/{session_id}")
async def delete_history(session_id: str):
    """清空对话历史"""
    count = clear_history(session_id)
    return {"session_id": session_id, "deleted": count}


@router.get("/status/{task_id}")
async def get_query_status(task_id: str):
    """查询任务状态"""
    status = get_task_status(task_id)
    from app.utils.task_utils import get_done_task_list, get_running_task_list
    return {
        "task_id": task_id,
        "status": status,
        "done_list": get_done_task_list(task_id),
        "running_list": get_running_task_list(task_id),
    }


@router.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "query"}


def _run_query(task_id: str, session_id: str, query: str):
    """后台线程执行查询流程"""
    update_task_status(task_id, TASK_STATUS_PROCESSING)

    try:
        initial_state = create_default_state(
            task_id=task_id,
            session_id=session_id,
            query=query,
            is_stream=True,
        )

        logger.info(f"查询流程启动: task_id={task_id}, session_id={session_id}, query={query[:50]}")

        # 执行 LangGraph 查询流程
        result = kb_query_app.invoke(initial_state)

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(f"查询流程完成: task_id={task_id}")

    except Exception as e:
        logger.error(f"查询流程失败: task_id={task_id}，错误: {str(e)}", exc_info=True)
        update_task_status(task_id, TASK_STATUS_FAILED)
        push_to_session(task_id, SSEEvent.ERROR, {"message": str(e)})
