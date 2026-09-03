"""
文档预览服务 FastAPI 路由（演进4 瘦身为控制器）
业务逻辑委托 DocumentService
"""
from fastapi import APIRouter, Query, Depends

from app.core.response import ok
from app.dependencies import get_document_service
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/list")
async def list_documents(service: DocumentService = Depends(get_document_service)):
    """获取所有已导入的文档列表（按 file_title 聚合）"""
    return ok(service.list_documents())


@router.get("/chunks/{file_title:path}")
async def get_document_chunks(
    file_title: str,
    limit: int = Query(500, ge=1, le=1000),
    service: DocumentService = Depends(get_document_service),
):
    """获取指定文档的切分详情，返回所有切片的标题、内容、文档主题等信息"""
    return ok(service.get_chunks(file_title, limit=limit))
