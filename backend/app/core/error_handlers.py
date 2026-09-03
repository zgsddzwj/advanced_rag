"""
全局异常处理器（演进2）
将业务异常 / 请求校验异常 / HTTPException / 未捕获异常
统一转换为响应信封，并记录结构化错误日志
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.logger import logger
from app.core.response import fail

# RequestValidationError 中每条错误的展示字段上限（防止超长请求刷屏）
_MAX_ERROR_ITEMS = 10


def register_error_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用上注册统一异常处理器"""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        """业务异常：按异常自带的状态码与错误码返回"""
        log = logger.warning if exc.status_code < 500 else logger.error
        log(f"业务异常: code={exc.code} status={exc.status_code} "
            f"path={request.url.path} message={exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.code, exc.message, details=exc.details or None),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(request: Request, exc: RequestValidationError):
        """请求体/参数校验失败：422 + 字段级错误明细"""
        errors = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])[1:]) or str(err.get("loc", "")),
                "message": err.get("msg", ""),
            }
            for err in exc.errors()[:_MAX_ERROR_ITEMS]
        ]
        return JSONResponse(
            status_code=422,
            content=fail(
                "REQUEST_VALIDATION_FAILED",
                "请求参数校验失败",
                details={"errors": errors},
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        """框架 HTTPException：包装为信封（404 SPA 回退在 main.py 单独处理）"""
        return JSONResponse(
            status_code=exc.status_code,
            content=fail("HTTP_ERROR", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_uncaught(request: Request, exc: Exception):
        """未捕获异常：500 + 脱敏消息（内部细节只进日志）"""
        logger.error(f"未捕获异常: path={request.url.path} error={exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=fail("INTERNAL_ERROR", "服务内部错误，请稍后重试"),
        )
