"""
文档预览服务 FastAPI 路由
提供已上传文档列表、切分详情预览 API
数据访问委托 app.repository.MilvusRepository（演进3）
"""
from typing import Dict, Any

from fastapi import APIRouter, Query

from app.core.exceptions import UpstreamServiceError
from app.core.response import ok
from app.core.logger import logger
from app.repository.milvus_repository import get_milvus_repository

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/list")
async def list_documents():
    """
    获取所有已导入的文档列表
    按 file_title 聚合，返回每个文档的切片数、文档主题等信息
    """
    try:
        all_data = get_milvus_repository().list_document_agg_rows()
        if not all_data:
            return ok({"documents": [], "total": 0})

        # 按 file_title 聚合（业务逻辑保留在服务层）
        doc_map: Dict[str, Dict[str, Any]] = {}
        for row in all_data:
            ft = row.get("file_title", "未知文档")
            if ft not in doc_map:
                doc_map[ft] = {
                    "file_title": ft,
                    "item_name": row.get("item_name", ""),
                    "chunk_count": 0,
                    "titles": [],
                }
            doc_map[ft]["chunk_count"] += 1
            title = row.get("title", "")
            if title and title not in doc_map[ft]["titles"]:
                doc_map[ft]["titles"].append(title)

        documents = list(doc_map.values())
        return ok({"documents": documents, "total": len(documents)})

    except UpstreamServiceError:
        raise
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}", exc_info=True)
        raise UpstreamServiceError("获取文档列表失败", upstream="milvus", details={"error": str(e)})


@router.get("/chunks/{file_title:path}")
async def get_document_chunks(file_title: str, limit: int = Query(500, ge=1, le=1000)):
    """获取指定文档的切分详情，返回所有切片的标题、内容、文档主题等信息"""
    try:
        chunks = get_milvus_repository().get_chunks(file_title, limit=limit)
        return ok({
            "file_title": file_title,
            "chunks": chunks,
            "total": len(chunks),
        })

    except UpstreamServiceError:
        raise
    except Exception as e:
        logger.error(f"获取文档切分详情失败: {str(e)}", exc_info=True)
        raise UpstreamServiceError("获取文档切分详情失败", upstream="milvus", details={"error": str(e)})
