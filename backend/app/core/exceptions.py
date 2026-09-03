"""
统一业务异常体系（演进2）
================================================
所有 API 层与领域层通过抛出 AppError 子类表达错误语义，
由全局异常处理器（app.core.error_handlers）统一转换为响应信封：

- 机器可读错误码（code）+ 人类可读消息（message）+ 可选细节（details）
- 明确的 HTTP 状态码映射，替代散落各处的 HTTPException 与 {"error": ...} 字典
- 上游依赖失败（Milvus/百炼/MinerU 等）统一归为 UpstreamServiceError(502)
"""
from typing import Any, Dict, Optional


class AppError(Exception):
    """业务异常基类"""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    default_message: str = "服务内部错误"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message or self.default_message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        super().__init__(self.message)


class BadRequestError(AppError):
    """请求参数非法（400）"""

    code = "BAD_REQUEST"
    status_code = 400
    default_message = "请求参数非法"


class FileValidationError(BadRequestError):
    """上传文件校验失败：格式不支持 / 超出大小限制（400）"""

    code = "FILE_INVALID"
    default_message = "文件校验失败"


class NotFoundError(AppError):
    """资源不存在（404）"""

    code = "NOT_FOUND"
    status_code = 404
    default_message = "资源不存在"


class ConflictError(AppError):
    """资源状态冲突（409）"""

    code = "CONFLICT"
    status_code = 409
    default_message = "资源状态冲突"


class UpstreamServiceError(AppError):
    """
    上游依赖服务失败：Milvus / MinIO / MongoDB / Kafka / 百炼 / MinerU 等（502）
    upstream 参数标明具体依赖，自动并入 details
    """

    code = "UPSTREAM_ERROR"
    status_code = 502
    default_message = "上游依赖服务暂时不可用"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        upstream: Optional[str] = None,
        **kwargs,
    ):
        details = dict(kwargs.pop("details", None) or {})
        if upstream:
            details.setdefault("upstream", upstream)
        super().__init__(message, details=details or None, **kwargs)


class InternalError(AppError):
    """未归类内部错误（500）"""

    code = "INTERNAL_ERROR"
    status_code = 500
    default_message = "服务内部错误"
