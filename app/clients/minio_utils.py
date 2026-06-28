"""
MinIO 客户端工具
负责文件上传、下载、桶管理
"""
import os
from minio import Minio
from app.core.logger import logger

_minio_client = None


def get_minio_client() -> Minio:
    """获取 MinIO 客户端单例"""
    global _minio_client
    if _minio_client is None:
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        bucket_name = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")

        _minio_client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )

        # 自动创建 bucket
        if not _minio_client.bucket_exists(bucket_name):
            _minio_client.make_bucket(bucket_name)
            logger.info(f"MinIO bucket 创建成功: {bucket_name}")

        logger.info(f"MinIO 客户端连接成功: {endpoint}")
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
    bucket_name = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")

    client.fput_object(
        bucket_name=bucket_name,
        object_name=object_name,
        file_path=local_path,
        content_type=content_type
    )

    # 构造访问 URL
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    url = f"http://{endpoint}/{bucket_name}/{object_name}"
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
    import io
    client = get_minio_client()
    bucket_name = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")

    client.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type
    )

    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    url = f"http://{endpoint}/{bucket_name}/{object_name}"
    logger.info(f"字节数据上传 MinIO 成功: {object_name} → {url}")
    return url
