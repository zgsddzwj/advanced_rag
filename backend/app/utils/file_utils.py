"""
上传文件安全工具
文件名校验/清洗与大小限制，供「上传导入」与「重导入」两条路径共用。
此前 reimport 路径直接拼接客户端文件名，存在路径遍历风险（upload 路径有防护），
统一收口到本模块后两条路径行为一致。
"""
import os
import re

from app.core.exceptions import FileValidationError

# 文件大小限制：100MB
MAX_FILE_SIZE = 100 * 1024 * 1024
# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".pdf", ".md"}


def sanitize_filename(filename: str) -> str:
    """
    安全化文件名：移除路径分隔符和特殊字符，防止目录遍历攻击
    """
    filename = os.path.basename(filename)
    filename = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', filename)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    return filename


def validate_upload_name(filename: str) -> str:
    """
    校验并清洗上传文件名
    :raises FileValidationError: 文件名为空或扩展名不受支持
    :return: 安全化后的文件名
    """
    if not filename:
        raise FileValidationError("文件名不能为空")
    safe = sanitize_filename(filename)
    ext = os.path.splitext(safe)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"不支持的文件格式: {ext}，仅支持 {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return safe
