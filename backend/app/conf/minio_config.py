"""
[兼容层] MinIO 配置
演进1 后所有配置统一由 app.conf.settings 提供，本模块仅为历史引用保留。
新代码请使用：from app.conf.settings import settings
"""
from app.conf.settings import settings


class MinioConfig:
    ENDPOINT = settings.minio_endpoint
    ACCESS_KEY = settings.minio_access_key
    SECRET_KEY = settings.minio_secret_key
    BUCKET_NAME = settings.minio_bucket_name
    SECURE = settings.minio_secure
    PDF_DIR = settings.minio_pdf_dir
    IMG_DIR = settings.minio_img_dir


minio_config = MinioConfig()
