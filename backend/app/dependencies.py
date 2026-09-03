"""
FastAPI 依赖注入提供者（演进4）
================================================
服务单例通过 lru_cache 提供，路由以 Depends() 注入：
替换实现（如测试中）只需覆盖依赖，路由代码零改动。
"""
from functools import lru_cache

from app.services.import_service import ImportService
from app.services.query_service import QueryService
from app.services.document_service import DocumentService


@lru_cache(maxsize=1)
def get_import_service() -> ImportService:
    return ImportService()


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    return QueryService()


@lru_cache(maxsize=1)
def get_document_service() -> DocumentService:
    return DocumentService()
