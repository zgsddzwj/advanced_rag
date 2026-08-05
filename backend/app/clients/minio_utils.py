"""
MinIO 客户端工具
负责文件上传、下载、桶管理
"""
import io
from typing import Optional
from minio import Minio
from app.core.logger import logger
from app.conf.minio_config import minio_config

_minio_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """获取 MinIO 客户端单例"""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            minio_config.ENDPOINT,
            access_key=minio_config.ACCESS_KEY,
            secret_key=minio_config.SECRET_KEY,
            secure=minio_config.SECURE,
        )

        # 自动创建 bucket
        if not _minio_client.bucket_exists(minio_config.BUCKET_NAME):
            _minio_client.make_bucket(minio_config.BUCKET_NAME)
            logger.info(f"MinIO bucket 创建成功: {minio_config.BUCKET_NAME}")

        logger.info(f"MinIO 客户端连接成功: {minio_config.ENDPOINT}")
    return _minio_client


def upload_file(local_path: str, object_name: str, content_type: str = "application/octet-stream") -> str:
    """
    上传文件到 MinIO
    :param local_path: 本地文件路径
    :param object_name: MinIO 中的对象名
    :param content_type: 文件 MIME 类型
    :return: MinIO 对象访问 URL
    """
    client = get_minio_client()

    client.fput_object(
        bucket_name=minio_config.BUCKET_NAME,
        object_name=object_name,
        file_path=local_path,
        content_type=content_type
    )

    # 构造访问 URL
    url = _build_object_url(object_name)
    logger.info(f"文件上传 MinIO 成功: {object_name} → {url}")
    return url


def upload_bytes(data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
    """
    上传字节数据到 MinIO
    :param data: 字节数据
    :param object_name: MinIO 中的对象名
    :param content_type: 文件 MIME 类型
    :return: MinIO 对象访问 URL
    """
    client = get_minio_client()

    client.put_object(
        bucket_name=minio_config.BUCKET_NAME,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type
    )

    url = _build_object_url(object_name)
    logger.info(f"字节数据上传 MinIO 成功: {object_name} → {url}")
    return url


def _build_object_url(object_name: str) -> str:
    """构造 MinIO 对象访问 URL"""
    protocol = "https" if minio_config.SECURE else "http"
    return f"{protocol}://{minio_config.ENDPOINT}/{minio_config.BUCKET_NAME}/{object_name}"
