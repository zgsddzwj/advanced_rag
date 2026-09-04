"""
文档服务（演进4）
文档列表/切片预览、删除与重导入事件发布
"""
import os
import uuid

from app.core.exceptions import NotFoundError, UpstreamServiceError
from app.core.logger import logger
from app.utils.path_util import PROJECT_ROOT
from app.clients.document_meta_utils import compute_content_hash
from app.clients.kafka_producer import publish_document_event
from app.repository.document_meta_repository import get_document_meta_repository
from app.repository.milvus_repository import get_milvus_repository

UPLOAD_DIR = PROJECT_ROOT / "uploads"


class DocumentService:
    """文档管理与预览用例服务"""

    def __init__(self, meta_repo=None, milvus_repo=None):
        self._meta_repo = meta_repo
        self._milvus_repo = milvus_repo

    @property
    def meta_repo(self):
        if self._meta_repo is None:
            self._meta_repo = get_document_meta_repository()
        return self._meta_repo

    @property
    def milvus_repo(self):
        if self._milvus_repo is None:
            self._milvus_repo = get_milvus_repository()
        return self._milvus_repo

    # ---------- 预览 ----------

    def list_documents(self) -> dict:
        """获取所有已导入文档列表（按 file_title 聚合）"""
        try:
            all_data = self.milvus_repo.list_document_agg_rows()
            if not all_data:
                return {"documents": [], "total": 0}

            doc_map: dict = {}
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

        except UpstreamServiceError:
            raise
        except Exception as e:
            logger.error(f"获取文档列表失败: {str(e)}", exc_info=True)
            raise UpstreamServiceError("获取文档列表失败", upstream="milvus", details={"error": str(e)})

    def get_chunks(self, file_title: str, limit: int = 500) -> dict:
        """获取指定文档的切片详情"""
        try:
            chunks = self.milvus_repo.get_chunks(file_title, limit=limit)
            return {"file_title": file_title, "chunks": chunks, "total": len(chunks)}
        except UpstreamServiceError:
            raise
        except Exception as e:
            logger.error(f"获取文档切分详情失败: {str(e)}", exc_info=True)
            raise UpstreamServiceError("获取文档切分详情失败", upstream="milvus", details={"error": str(e)})

    # ---------- 删除 / 重导入（Kafka 事件驱动） ----------

    async def delete_document(self, file_title: str) -> dict:
        """
        删除文档：发布 DOCUMENT_DELETE 事件
        Kafka 消费者将异步删除 Milvus 中的 chunks 和元数据
        """
        meta = self.meta_repo.get(file_title)
        if not meta:
            # 元数据缺失时回查 Milvus，避免误删仍有索引数据的文档
            try:
                if not self.milvus_repo.has_chunks(file_title):
                    raise NotFoundError(f"文档不存在: {file_title}")
            except NotFoundError:
                raise
            except Exception as e:
                logger.warning(f"检查 Milvus 文档存在性失败: {e}")

        await publish_document_event(
            event_type="DOCUMENT_DELETE",
            file_title=file_title,
        )
        logger.info(f"文档删除事件已发布: {file_title}")
        return {
            "file_title": file_title,
            "status": "deleting",
            "message": "删除请求已提交，Kafka 消费者将异步处理",
        }

    async def reimport_document(self, file_title: str, upload) -> dict:
        """
        重新导入文档：流式保存新版本文件，发布 UPDATE/ADD 事件
        Kafka 消费者将先删除旧 chunks，再重新导入
        :param upload: 上传流（filename + async read）
        """
        filename = upload.filename or ""
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        task_id = str(uuid.uuid4())[:8]
        saved_filename = f"{task_id}_{filename}"
        saved_path = UPLOAD_DIR / saved_filename
        with open(saved_path, "wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        content_hash = compute_content_hash(str(saved_path))
        meta = self.meta_repo.get(file_title)
        event_type = "DOCUMENT_UPDATE" if meta else "DOCUMENT_ADD"

        await publish_document_event(
            event_type=event_type,
            file_title=file_title,
            file_path=str(saved_path),
            content_hash=content_hash,
        )
        logger.info(f"文档重新导入事件已发布: {file_title}, type={event_type}")
        return {
            "file_title": file_title,
            "status": "processing",
            "event_type": event_type,
            "content_hash": content_hash[:12],
            "message": "重新导入请求已提交，Kafka 消费者将异步处理",
        }

    def list_meta(self) -> dict:
        """列出所有文档元数据（含同步状态）"""
        docs = self.meta_repo.list_all()
        return {"documents": docs, "total": len(docs)}
