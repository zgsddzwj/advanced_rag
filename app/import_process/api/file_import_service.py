"""
导入服务 FastAPI 路由
提供文件上传和导入流程触发的 REST API
"""
import os
import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse

from app.core.logger import logger
from app.utils.path_util import PROJECT_ROOT
from app.utils.task_utils import update_task_status, get_task_status, TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED
from app.import_process.agent.main_graph import kb_import_app
from app.import_process.agent.state import create_default_state

router = APIRouter(prefix="/import", tags=["import"])

UPLOAD_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "output"


@router.get("/", response_class=HTMLResponse)
async def import_page():
    """导入页面"""
    html_path = Path(__file__).parent.parent / "page" / "import.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>import.html not found</h1>")


@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    上传文件并触发导入流程
    返回 task_id 供前端轮询
    """
    # 生成唯一 task_id
    task_id = str(uuid.uuid4())[:8]

    # 保存文件
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    saved_filename = f"{task_id}_{file.filename}"
    saved_path = UPLOAD_DIR / saved_filename

    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    logger.info(f"文件上传成功: {saved_filename}，task_id: {task_id}")

    # 创建输出目录
    output_dir = OUTPUT_DIR / f"{task_id}_{os.path.splitext(file.filename)[0]}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 后台执行导入流程
    background_tasks.add_task(_run_import, task_id, str(saved_path), str(output_dir))

    return {"task_id": task_id, "filename": file.filename, "status": "processing"}


@router.get("/status/{task_id}")
async def get_import_status(task_id: str):
    """查询导入任务状态"""
    status = get_task_status(task_id)
    from app.utils.task_utils import get_done_task_list, get_running_task_list
    return {
        "task_id": task_id,
        "status": status,
        "done_list": get_done_task_list(task_id),
        "running_list": get_running_task_list(task_id)
    }


def _run_import(task_id: str, file_path: str, output_dir: str):
    """后台执行导入流程"""
    update_task_status(task_id, TASK_STATUS_PROCESSING)

    try:
        initial_state = create_default_state(
            task_id=task_id,
            local_file_path=file_path,
            local_dir=output_dir,
        )

        # 同步执行 LangGraph 流程
        result = kb_import_app.invoke(initial_state)

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(f"导入流程完成，task_id: {task_id}")

    except Exception as e:
        logger.error(f"导入流程失败，task_id: {task_id}，错误: {str(e)}", exc_info=True)
        update_task_status(task_id, TASK_STATUS_FAILED)
