"""
查询服务 FastAPI 路由（演进4 瘦身为控制器）
提供智能问答的 REST API，支持 SSE 流式输出
业务逻辑委托 QueryService
"""
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.core.response import ok
from app.dependencies import get_query_service
from app.services.query_service import QueryService
from app.utils.sse_utils import sse_generator
from app.utils.task_utils import (
    get_task_status, get_done_task_list, get_running_task_list,
)

router = APIRouter(prefix="/query", tags=["query"])


class RetrievalOptions(BaseModel):
    """
    按请求检索策略（演进7）：全部字段可选，缺省沿用服务端默认值
    """
    enable_hyde: Optional[bool] = Field(None, description="是否执行 HyDE 补充检索")
    enable_web_search: Optional[bool] = Field(
        None, description="联网搜索三态开关：缺省=按结果数自动判断"
    )
    top_k: Optional[int] = Field(None, ge=1, le=30, description="每路检索返回文档数")
    rrf_k: Optional[int] = Field(None, ge=1, le=1000, description="RRF 平滑因子")
    rrf_output_limit: Optional[int] = Field(None, ge=1, le=50, description="RRF 融合后数量上限")
    web_search_count: Optional[int] = Field(None, ge=1, le=20, description="联网搜索结果数")


class QueryRequest(BaseModel):
    """查询请求"""
    query: str
    session_id: str = ""
    retrieval: Optional[RetrievalOptions] = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """校验查询文本"""
        v = v.strip()
        if not v:
            raise ValueError("查询内容不能为空")
        if len(v) > 2000:
            raise ValueError("查询内容过长，请限制在 2000 字以内")
        return v


@router.post("/ask")
async def ask(req: QueryRequest, service: QueryService = Depends(get_query_service)):
    """
    提交查询，返回 session_id 和 task_id
    前端通过 /query/stream/{task_id} 接收 SSE 流式回答
    retrieval 可选携带检索策略（HyDE/联网搜索开关、top_k、RRF 参数）
    """
    retrieval_config = req.retrieval.model_dump(exclude_none=True) if req.retrieval else {}
    return ok(service.ask(req.query, req.session_id, retrieval_config=retrieval_config))


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
async def get_history(session_id: str, service: QueryService = Depends(get_query_service)):
    """获取对话历史"""
    return ok({"session_id": session_id, "messages": service.get_history(session_id)})


@router.delete("/history/{session_id}")
async def delete_history(session_id: str, service: QueryService = Depends(get_query_service)):
    """清空对话历史"""
    count = service.clear_history(session_id)
    return ok({"session_id": session_id, "deleted": count})


@router.get("/status/{task_id}")
async def get_query_status(task_id: str):
    """查询任务状态"""
    return ok({
        "task_id": task_id,
        "status": get_task_status(task_id),
        "done_list": get_done_task_list(task_id),
        "running_list": get_running_task_list(task_id),
    })


@router.get("/health")
async def health():
    """健康检查"""
    return ok({"status": "ok", "service": "query"})
