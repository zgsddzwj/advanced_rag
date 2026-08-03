"""MinIO 配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class MinioConfig:
    """MinIO 客户端配置"""
    ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")
    SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"
    PDF_DIR = os.getenv("MINIO_PDF_DIR", "pdf_files")
    IMG_DIR = os.getenv("MINIO_IMG_DIR", "images")


minio_config = MinioConfig()
