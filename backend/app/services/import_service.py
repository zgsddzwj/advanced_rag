"""
导入服务（演进4）
文件上传校验、导入任务编排（LangGraph 后台执行）、元数据落库与事件发布
"""
import asyncio
import os
import re
import uuid
from typing import Protocol

from app.core.exceptions import FileValidationError
from app.core.logger import logger
from app.utils.path_util import PROJECT_ROOT
from app.utils.task_utils import (
    update_task_status, get_task_status,
    get_done_task_list, get_running_task_list,
    TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
)
from app.repository.document_meta_repository import get_document_meta_repository
from app.clients.document_meta_utils import compute_content_hash
from app.clients.kafka_producer import publish_document_event

UPLOAD_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "output"

# 文件大小限制：100MB
MAX_FILE_SIZE = 100 * 1024 * 1024
# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".pdf", ".md"}
# 流式落盘的读取块大小（1MB）
UPLOAD_CHUNK_SIZE = 1024 * 1024


class UploadStream(Protocol):
    """上传流协议：与 fastapi.UploadFile 结构兼容，便于测试替身"""

    filename: str

    async def read(self, size: int = -1) -> bytes:
        ...


class ImportService:
    """文档导入用例服务"""

    def __init__(self, meta_repo=None):
        self._meta_repo = meta_repo

    @property
    def meta_repo(self):
        if self._meta_repo is None:
            self._meta_repo = get_document_meta_repository()
        return self._meta_repo

    # ---------- 上传 ----------

    async def submit_upload(self, upload: UploadStream, background_tasks) -> dict:
        """
        校验并保存上传文件，注册后台导入任务
        文件流式落盘（按块读取），避免大文件整体读入内存
        :param upload: 上传流（filename + async read）
        :param background_tasks: FastAPI BackgroundTasks
        :return: {task_id, filename, status}
        """
        filename = upload.filename or ""
        if not filename:
            raise FileValidationError("文件名不能为空")

        safe_filename = _sanitize_filename(filename)
        file_ext = os.path.splitext(safe_filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"不支持的文件格式: {file_ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"
            )

        task_id = str(uuid.uuid4())[:8]

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        saved_filename = f"{task_id}_{safe_filename}"
        saved_path = UPLOAD_DIR / saved_filename

        # 流式写入 + 大小限制（超限即中止并清理半截文件）
        size = 0
        try:
            with open(saved_path, "wb") as f:
                while True:
                    chunk = await upload.read(UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_FILE_SIZE:
                        raise FileValidationError(
                            f"文件大小超过限制（上限 {MAX_FILE_SIZE / 1024 / 1024:.0f}MB）",
                            code="FILE_TOO_LARGE",
                        )
                    f.write(chunk)
        except Exception:
            saved_path.unlink(missing_ok=True)
            raise

        logger.info(
            f"文件上传成功: {saved_filename}，task_id: {task_id}，"
            f"大小: {size / 1024:.0f}KB"
        )

        file_stem = os.path.splitext(safe_filename)[0]
        output_dir = OUTPUT_DIR / f"{task_id}_{file_stem}"
        output_dir.mkdir(parents=True, exist_ok=True)

        background_tasks.add_task(self.run_import, task_id, str(saved_path), str(output_dir))
        return {"task_id": task_id, "filename": safe_filename, "status": "processing"}

    # ---------- 状态查询 ----------

    def get_task_status(self, task_id: str) -> dict:
        status = get_task_status(task_id)
        return {
            "task_id": task_id,
            "status": status,
            "done_list": get_done_task_list(task_id),
            "running_list": get_running_task_list(task_id),
        }

    # ---------- 后台导入流程 ----------

    def run_import(self, task_id: str, file_path: str, output_dir: str):
        """后台执行导入流程，完成后保存元数据并发布 Kafka 事件"""
        update_task_status(task_id, TASK_STATUS_PROCESSING)

        try:
            from app.import_process.agent.main_graph import kb_import_app
            from app.import_process.agent.state import create_default_state

            initial_state = create_default_state(
                task_id=task_id,
                local_file_path=file_path,
                local_dir=output_dir,
            )

            # 同步执行 LangGraph 流程
            result = kb_import_app.invoke(initial_state)

            chunks = result.get("chunks", [])
            item_name = result.get("item_name", "")
            file_title = result.get("file_title", "")
            chunk_count = len(chunks)

            # 保存文档元数据到 MongoDB
            content_hash = compute_content_hash(file_path)
            old_meta = self.meta_repo.upsert(
                file_title=file_title,
                content_hash=content_hash,
                chunk_count=chunk_count,
                item_name=item_name,
                file_path=file_path,
            )

            # 判断事件类型：有旧记录且哈希不同 → UPDATE，否则 → ADD
            old_hash = old_meta.get("content_hash", "") if old_meta else ""
            event_type = "DOCUMENT_UPDATE" if old_hash and old_hash != content_hash else "DOCUMENT_ADD"

            # 发布 Kafka 事件（同步函数中创建事件循环）
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(publish_document_event(
                    event_type=event_type,
                    file_title=file_title,
                    file_path=file_path,
                    content_hash=content_hash,
                    chunk_count=chunk_count,
                    item_name=item_name,
                ))
                loop.close()
            except Exception as e:
                logger.warning(f"Kafka 事件发布失败（不影响导入结果）: {e}")

            update_task_status(task_id, TASK_STATUS_COMPLETED)
            logger.info(f"导入流程完成，task_id: {task_id}, chunks: {chunk_count}, event: {event_type}")

        except Exception as e:
            logger.error(f"导入流程失败，task_id: {task_id}，错误: {str(e)}", exc_info=True)
            update_task_status(task_id, TASK_STATUS_FAILED)


def _sanitize_filename(filename: str) -> str:
    """
    安全化文件名：移除路径分隔符和特殊字符
    防止目录遍历攻击
    """
    filename = os.path.basename(filename)
    filename = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', filename)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    return filename
