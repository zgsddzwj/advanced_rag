"""
导入服务 FastAPI 路由
提供文件上传和导入流程触发的 REST API
导入完成后自动发布 Kafka 事件，驱动文档元数据同步
"""
import os
import asyncio
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException

from app.core.logger import logger
from app.utils.path_util import PROJECT_ROOT
from app.utils.task_utils import (
    update_task_status, get_task_status,
    get_done_task_list, get_running_task_list,
    TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
)
from app.import_process.agent.main_graph import kb_import_app
from app.import_process.agent.state import create_default_state
from app.clients.document_meta_utils import compute_content_hash, get_metadata, upsert_metadata
from app.clients.kafka_producer import publish_document_event

router = APIRouter(prefix="/import", tags=["import"])

UPLOAD_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "output"

# 文件大小限制：100MB
MAX_FILE_SIZE = 100 * 1024 * 1024
# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".pdf", ".md"}


def _sanitize_filename(filename: str) -> str:
    """
    安全化文件名：移除路径分隔符和特殊字符
    防止目录遍历攻击
    """
    # 仅保留文件名部分（去除路径）
    filename = os.path.basename(filename)
    # 移除控制字符和特殊字符
    filename = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', filename)
    # 限制长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    return filename


@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    上传文件并触发导入流程
    返回 task_id 供前端轮询
    """
    # 校验文件名和扩展名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    safe_filename = _sanitize_filename(file.filename)
    file_ext = os.path.splitext(safe_filename)[1].lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 生成唯一 task_id
    task_id = str(uuid.uuid4())[:8]

    # 保存文件（带大小校验）
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_filename = f"{task_id}_{safe_filename}"
    saved_path = UPLOAD_DIR / saved_filename

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制: {len(content) / 1024 / 1024:.1f}MB > {MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
        )

    with open(saved_path, "wb") as f:
        f.write(content)

    logger.info(f"文件上传成功: {saved_filename}，task_id: {task_id}，大小: {len(content) / 1024:.0f}KB")

    # 创建输出目录
    file_stem = os.path.splitext(safe_filename)[0]
    output_dir = OUTPUT_DIR / f"{task_id}_{file_stem}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 后台执行导入流程
    background_tasks.add_task(_run_import, task_id, str(saved_path), str(output_dir))

    return {"task_id": task_id, "filename": safe_filename, "status": "processing"}


@router.get("/status/{task_id}")
async def get_import_status(task_id: str):
    """查询导入任务状态"""
    status = get_task_status(task_id)
    return {
        "task_id": task_id,
        "status": status,
        "done_list": get_done_task_list(task_id),
        "running_list": get_running_task_list(task_id)
    }


@router.get("/health")
async def health():
    """导入服务健康检查"""
    return {"status": "ok", "service": "import"}


def _run_import(task_id: str, file_path: str, output_dir: str):
    """后台执行导入流程，完成后保存元数据并发布 Kafka 事件"""
    update_task_status(task_id, TASK_STATUS_PROCESSING)

    try:
        initial_state = create_default_state(
            task_id=task_id,
            local_file_path=file_path,
            local_dir=output_dir,
        )

        # 同步执行 LangGraph 流程
        result = kb_import_app.invoke(initial_state)

        # 提取导入结果
        chunks = result.get("chunks", [])
        item_name = result.get("item_name", "")
        file_title = result.get("file_title", "")
        chunk_count = len(chunks)

        # 保存文档元数据到 MongoDB
        content_hash = compute_content_hash(file_path)
        old_meta = upsert_metadata(
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
