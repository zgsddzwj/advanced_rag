"""
文档事件 API（演进4 瘦身为控制器）
提供文档删除、重新导入等端点，通过 Kafka 发布事件触发异步处理。
业务逻辑委托 DocumentService
"""
from fastapi import APIRouter, UploadFile, File, Depends

from app.core.response import ok
from app.dependencies import get_document_service
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.delete("/{file_title:path}")
async def delete_document(
    file_title: str,
    service: DocumentService = Depends(get_document_service),
):
    """
    删除文档：发布 DOCUMENT_DELETE 事件
    Kafka 消费者将异步删除 Milvus 中的 chunks 和元数据
    """
    result = await service.delete_document(file_title)
    return ok(result)


@router.post("/reimport/{file_title:path}")
async def reimport_document(
    file_title: str,
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    """
    重新导入文档：上传新版本文件，发布 DOCUMENT_UPDATE 事件
    Kafka 消费者将先删除旧 chunks，再重新导入
    """
    result = await service.reimport_document(file_title, file)
    return ok(result)


@router.get("/meta/list")
async def list_document_meta(service: DocumentService = Depends(get_document_service)):
    """列出所有文档的元数据（含同步状态）"""
    return ok(service.list_meta())
