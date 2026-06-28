"""
FastAPI 主应用入口
整合导入和查询两个子服务
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.core.logger import logger
from app.import_process.api.file_import_service import router as import_router
from app.query_process.api.query_service import router as query_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("===== Advanced RAG 服务启动 =====")
    yield
    logger.info("===== Advanced RAG 服务关闭 =====")


app = FastAPI(title="Advanced RAG", lifespan=lifespan)

# 注册路由
app.include_router(import_router, prefix="/api")
app.include_router(query_router, prefix="/api")


@app.get("/")
async def root():
    """根路径重定向到导入页面"""
    return RedirectResponse(url="/api/import/")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
