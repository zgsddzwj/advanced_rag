"""
[兼容层] 文档元数据管理工具
演进3 后元数据访问统一由 app.repository.document_meta_repository 提供，
本模块保留文件哈希工具并为历史引用做委托。
新代码请使用：
    from app.repository import get_document_meta_repository
"""
import hashlib

from app.core.logger import logger
from app.repository.document_meta_repository import get_document_meta_repository


def compute_content_hash(file_path: str) -> str:
    """计算文件内容的 MD5 哈希（hashlib.file_digest 大块读取，减少大文件 IO 次数）"""
    try:
        with open(file_path, "rb") as f:
            return hashlib.file_digest(f, "md5").hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败: {file_path}, {e}")
        return ""


def upsert_metadata(
    file_title: str,
    content_hash: str,
    chunk_count: int = 0,
    item_name: str = "",
    file_path: str = "",
) -> dict:
    """插入或更新文档元数据，返回旧元数据（委托仓储）"""
    return get_document_meta_repository().upsert(
        file_title=file_title,
        content_hash=content_hash,
        chunk_count=chunk_count,
        item_name=item_name,
        file_path=file_path,
    )


def get_metadata(file_title: str):
    """查询文档元数据（委托仓储）"""
    return get_document_meta_repository().get(file_title)


def delete_metadata(file_title: str) -> bool:
    """删除文档元数据（委托仓储）"""
    return get_document_meta_repository().delete(file_title)


def mark_status(file_title: str, status: str):
    """更新文档状态 (委托仓储)"""
    get_document_meta_repository().mark_status(file_title, status)


def list_all_metadata() -> list:
    """列出所有文档元数据（委托仓储）"""
    return get_document_meta_repository().list_all()
