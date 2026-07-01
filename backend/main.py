"""
FastAPI 主应用入口
整合前端静态文件服务和后端 API 路由
"""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.core.logger import logger
from app.conf.lm_config import lm_config
from app.conf.mineru_config import mineru_config
from app.conf.bailian_mcp_config import bailian_mcp_config
from app.import_process.api.file_import_service import router as import_router
from app.query_process.api.query_service import router as query_router

# 前端构建产物目录（frontend/dist/）
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("===== Advanced RAG 服务启动 =====")

    # 校验百炼 API Key
    api_key = lm_config.DASHSCOPE_API_KEY
    if not api_key or api_key.startswith("sk-xxxx"):
        logger.warning("⚠️  DASHSCOPE_API_KEY 未配置或为占位符！")
        logger.warning("⚠️  请在项目根目录 .env 文件中填入真实的阿里云百炼 API Key")
        logger.warning("⚠️  获取地址: https://bailian.console.aliyun.com/ → 模型广场 → API Key")
    else:
        logger.info(f"百炼 API Key 已配置: {api_key[:8]}...{api_key[-4:]}")

    # 校验 MinerU API Token（PDF 导入需要）
    mineru_token = mineru_config.API_TOKEN
    if not mineru_token or mineru_token.startswith("your_"):
        logger.warning("⚠️  MINERU_API_TOKEN 未配置或为占位符！PDF 导入功能将不可用")
        logger.warning("⚠️  获取地址: https://mineru.net/ → 个人中心 → API Token")
    else:
        logger.info(f"MinerU API Token 已配置: {mineru_token[:8]}...")

    # 校验百炼 MCP App ID（网络搜索需要）
    mcp_app_id = bailian_mcp_config.BAILIAN_MCP_APP_ID
    if not mcp_app_id or mcp_app_id.startswith("your_"):
        logger.warning("⚠️  BAILIAN_MCP_APP_ID 未配置或为占位符！网络搜索功能将不可用")
        logger.warning("⚠️  获取地址: https://bailian.console.aliyun.com/ → 应用广场 → 创建应用")
    else:
        logger.info(f"百炼 MCP App ID 已配置: {mcp_app_id}")

    yield
    logger.info("===== Advanced RAG 服务关闭 =====")


app = FastAPI(title="Advanced RAG", lifespan=lifespan)

# 注册后端 API 路由
app.include_router(import_router, prefix="/api")
app.include_router(query_router, prefix="/api")

# 挂载前端静态资源 (CSS/JS/assets)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


# ==================== 前端页面路由 (SPA) ====================

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
