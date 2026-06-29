"""
FastAPI 主应用入口
整合前端静态文件服务和后端 API 路由
"""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from app.core.logger import logger
from app.import_process.api.file_import_service import router as import_router
from app.query_process.api.query_service import router as query_router

# 前端静态文件目录
FRONTEND_DIR = Path(__file__).parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("===== Advanced RAG 服务启动 =====")
    yield
    logger.info("===== Advanced RAG 服务关闭 =====")


app = FastAPI(title="Advanced RAG", lifespan=lifespan)

# 挂载前端静态资源 (CSS/JS)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# 注册后端 API 路由
app.include_router(import_router, prefix="/api")
app.include_router(query_router, prefix="/api")


# ==================== 前端页面路由 ====================

@app.get("/")
async def index():
    """首页"""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/import")
async def import_page():
    """知识库导入页面"""
    return FileResponse(str(FRONTEND_DIR / "import.html"))


@app.get("/chat")
async def chat_page():
    """智能问答页面"""
    return FileResponse(str(FRONTEND_DIR / "chat.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
