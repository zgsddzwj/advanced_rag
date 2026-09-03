"""
文档事件 API
提供文档删除、重新导入等端点，通过 Kafka 发布事件触发异步处理。
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from app.core.exceptions import NotFoundError
from app.core.response import ok
from app.core.logger import logger
from app.utils.path_util import PROJECT_ROOT
from app.clients.document_meta_utils import compute_content_hash
from app.repository.document_meta_repository import get_document_meta_repository
from app.repository.milvus_repository import get_milvus_repository
from app.clients.kafka_producer import publish_document_event

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = PROJECT_ROOT / "uploads"


class ReimportResponse(BaseModel):
    file_title: str
    status: str
    event_id: str


@router.delete("/{file_title:path}")
async def delete_document(file_title: str):
    """
    删除文档：发布 DOCUMENT_DELETE 事件
    Kafka 消费者将异步删除 Milvus 中的 chunks 和元数据
    """
    # 检查文档是否存在
    meta_repo = get_document_meta_repository()
    milvus_repo = get_milvus_repository()
    meta = meta_repo.get(file_title)
    if not meta:
        # 元数据缺失时回查 Milvus，避免误删仍有索引数据的文档
        try:
            if not milvus_repo.has_chunks(file_title):
                raise NotFoundError(f"文档不存在: {file_title}")
        except NotFoundError:
            raise
        except Exception as e:
            logger.warning(f"检查 Milvus 文档存在性失败: {e}")

    # 发布删除事件
    event_id = str(uuid.uuid4())[:8]
    await publish_document_event(
        event_type="DOCUMENT_DELETE",
        file_title=file_title,
    )

    logger.info(f"文档删除事件已发布: {file_title}, event_id={event_id}")
    return ok({
        "file_title": file_title,
        "status": "deleting",
        "event_id": event_id,
        "message": "删除请求已提交，Kafka 消费者将异步处理",
    })


@router.post("/reimport/{file_title:path}")
async def reimport_document(file_title: str, file: UploadFile = File(...)):
    """
    重新导入文档：上传新版本文件，发布 DOCUMENT_UPDATE 事件
    Kafka 消费者将先删除旧 chunks，再重新导入
    """
    # 保存上传的文件
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    task_id = str(uuid.uuid4())[:8]
    saved_filename = f"{task_id}_{file.filename}"
    saved_path = UPLOAD_DIR / saved_filename

    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 计算内容哈希
    content_hash = compute_content_hash(str(saved_path))

    # 检查是否有旧文档
    meta = get_document_meta_repository().get(file_title)
    event_type = "DOCUMENT_UPDATE" if meta else "DOCUMENT_ADD"

    # 发布事件
    await publish_document_event(
        event_type=event_type,
        file_title=file_title,
        file_path=str(saved_path),
        content_hash=content_hash,
    )

    logger.info(f"文档重新导入事件已发布: {file_title}, type={event_type}")
    return ok({
        "file_title": file_title,
        "status": "processing",
        "event_type": event_type,
        "content_hash": content_hash[:12],
        "message": "重新导入请求已提交，Kafka 消费者将异步处理",
    })


@router.get("/meta/list")
async def list_document_meta():
    """列出所有文档的元数据（含同步状态）"""
    docs = get_document_meta_repository().list_all()
    return ok({"documents": docs, "total": len(docs)})
