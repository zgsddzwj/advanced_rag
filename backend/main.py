"""
FastAPI 主应用入口
整合前端静态文件服务和后端 API 路由
"""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException

from app.core.logger import logger
from app.conf.settings import settings
from app.import_process.api.file_import_service import router as import_router
from app.import_process.api.document_preview_service import router as document_router
from app.import_process.api.document_event_service import router as document_event_router
from app.query_process.api.query_service import router as query_router
from app.clients.kafka_consumer import start_kafka_consumer, stop_kafka_consumer
from app.clients.kafka_producer import close_producer

# 前端构建产物目录（frontend/dist/）
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("===== Advanced RAG 服务启动 =====")

    # 输出配置摘要（敏感项已脱敏），并校验关键配置
    logger.info(f"运行配置: {settings.describe()}")

    if settings.dashscope_key_configured:
        logger.info("百炼 API Key 已配置")
    else:
        logger.warning("⚠️  DASHSCOPE_API_KEY 未配置或为占位符！")
        logger.warning("⚠️  请在 backend/.env 文件中填入真实的阿里云百炼 API Key")
        logger.warning("⚠️  获取地址: https://bailian.console.aliyun.com/ → 模型广场 → API Key")

    if settings.mineru_token_configured:
        logger.info("MinerU API Token 已配置")
    else:
        logger.warning("⚠️  MINERU_API_TOKEN 未配置或为占位符！PDF 导入功能将不可用")
        logger.warning("⚠️  获取地址: https://mineru.net/ → 个人中心 → API Token")

    if settings.bailian_mcp_configured:
        logger.info("百炼 MCP App ID 已配置")
    else:
        logger.warning("⚠️  BAILIAN_MCP_APP_ID 未配置或为占位符！网络搜索功能将不可用")
        logger.warning("⚠️  获取地址: https://bailian.console.aliyun.com/ → 应用广场 → 创建应用")

    if settings.kafka_enabled:
        logger.info(
            f"Kafka 已启用: brokers={settings.kafka_bootstrap_servers}, "
            f"topic={settings.kafka_topic}"
        )
        # 启动 Kafka 消费者
        await start_kafka_consumer()
    else:
        logger.info("Kafka 未启用，文档事件同步功能不可用")

    yield
    logger.info("===== Advanced RAG 服务关闭 =====")

    # 停止 Kafka 消费者和生产者
    await stop_kafka_consumer()
    await close_producer()


app = FastAPI(title="NexusRAG", lifespan=lifespan)

# CORS 中间件：允许开发模式下 Vite 开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册后端 API 路由
app.include_router(import_router, prefix="/api")
app.include_router(document_router, prefix="/api")
app.include_router(document_event_router, prefix="/api")
app.include_router(query_router, prefix="/api")

# 挂载前端静态资源 (CSS/JS/assets)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


# ==================== 前端页面路由 (SPA) ====================

# 已知的前端路由列表
SPA_ROUTES = {"/", "/import", "/chat"}


@app.get("/")
async def index():
    """首页"""
    return FileResponse(str(FRONTEND_DIST / "index.html"))


@app.get("/import")
async def import_page():
    """知识库导入页面 — SPA 路由回退"""
    return FileResponse(str(FRONTEND_DIST / "index.html"))


@app.get("/chat")
async def chat_page():
    """智能问答页面 — SPA 路由回退"""
    return FileResponse(str(FRONTEND_DIST / "index.html"))


@app.get("/documents")
async def documents_page():
    """文档预览页面 — SPA 路由回退"""
    return FileResponse(str(FRONTEND_DIST / "index.html"))


@app.exception_handler(404)
async def spa_fallback(request: Request, exc: HTTPException):
    """SPA 路由回退：非 API 路径的 404 返回 index.html，支持前端客户端路由"""
    path = request.url.path
    # API 路径返回标准 JSON 404
    if path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    # 前端静态资源路径返回标准 404
    if path.startswith("/assets/"):
        return JSONResponse(status_code=404, content={"detail": "Asset Not Found"})
    # 其他路径回退到 index.html（SPA 客户端路由）
    if FRONTEND_DIST.exists():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        timeout_graceful_shutdown=10,
    )
