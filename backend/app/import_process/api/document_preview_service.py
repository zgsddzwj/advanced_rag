"""
文档预览服务 FastAPI 路由
提供已上传文档列表、切分详情预览 API
"""
from typing import List, Dict, Any

from fastapi import APIRouter, Query

from app.core.logger import logger
from app.clients.milvus_utils import get_milvus_client
from app.utils.escape_milvus_string_utils import escape_milvus_string
from app.conf.settings import settings

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/list")
async def list_documents():
    """
    获取所有已导入的文档列表
    按 file_title 聚合，返回每个文档的切片数、文档主题等信息
    优化：只查询聚合所需字段，减少数据传输量
    """
    try:
        client = get_milvus_client()
        collection_name = settings.chunks_collection

        if not client.has_collection(collection_name=collection_name):
            return {"documents": [], "total": 0}

        client.load_collection(collection_name=collection_name)

        # 只查询聚合所需字段，避免传输全量 content
        all_data = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["file_title", "item_name", "title"],
            limit=16384,
        )

        if not all_data:
            return {"documents": [], "total": 0}

        # 按 file_title 聚合
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
        return {"documents": documents, "total": len(documents)}

    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}", exc_info=True)
        return {"documents": [], "total": 0, "error": str(e)}


@router.get("/chunks/{file_title:path}")
async def get_document_chunks(file_title: str, limit: int = Query(500, ge=1, le=1000)):
    """
    获取指定文档的切分详情
    返回所有切片的标题、内容、文档主题等信息
    """
    try:
        client = get_milvus_client()
        collection_name = settings.chunks_collection

        if not client.has_collection(collection_name=collection_name):
            return {"file_title": file_title, "chunks": [], "total": 0}

        client.load_collection(collection_name=collection_name)

        safe_title = escape_milvus_string(file_title)

        chunks = client.query(
            collection_name=collection_name,
            filter=f'file_title=="{safe_title}"',
            output_fields=["title", "parent_title", "part", "content", "item_name", "file_title"],
            limit=limit,
        )

        # 按 part 排序
        chunks.sort(key=lambda x: x.get("part", 0))

        return {
            "file_title": file_title,
            "chunks": chunks,
            "total": len(chunks),
        }

    except Exception as e:
        logger.error(f"获取文档切分详情失败: {str(e)}", exc_info=True)
        return {"file_title": file_title, "chunks": [], "total": 0, "error": str(e)}
