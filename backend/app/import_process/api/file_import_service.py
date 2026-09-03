"""
导入服务 FastAPI 路由（演进4 瘦身为控制器）
业务逻辑委托 ImportService，本文件只做请求解析与信封包装
"""
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends

from app.core.response import ok
from app.dependencies import get_import_service
from app.services.import_service import ImportService

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service: ImportService = Depends(get_import_service),
):
    """
    上传文件并触发导入流程
    返回 task_id 供前端轮询
    """
    content = await file.read()
    result = service.submit_upload(content, file.filename or "", background_tasks)
    return ok(result)


@router.get("/status/{task_id}")
async def get_import_status(task_id: str, service: ImportService = Depends(get_import_service)):
    """查询导入任务状态"""
    return ok(service.get_task_status(task_id))


@router.get("/health")
async def health():
    """导入服务健康检查"""
    return ok({"status": "ok", "service": "import"})
