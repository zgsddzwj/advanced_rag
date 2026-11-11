"""
file_utils 边界用例补充：扩展名大小写、超长文件名截断
"""
import pytest

from app.core.exceptions import FileValidationError
from app.utils.file_utils import sanitize_filename, validate_upload_name


class TestFileUtilsEdgeCases:
    def test_uppercase_extension_accepted(self):
        """扩展名大小写不敏感：.PDF/.Md 是合法上传"""
        assert validate_upload_name("报告.PDF") == "报告.PDF"
        assert validate_upload_name("notes.Md") == "notes.Md"

    def test_long_filename_truncated_keeps_extension(self):
        """超过 200 字符的文件名截断时必须保留扩展名"""
        long_name = "长" * 300 + ".pdf"
        safe = sanitize_filename(long_name)
        assert len(safe) <= 200
        assert safe.endswith(".pdf")

    def test_validate_rejects_extension_only_traversal(self):
        """多层目录 + 非法字符混合的路径清洗后不再含分隔符"""
        safe = validate_upload_name("..\\..\\evil\"file.pdf")
        assert "/" not in safe and "\\" not in safe and '"' not in safe

    def test_validate_rejects_hidden_double_ext(self):
        """.pdf.exe 这类伪装扩展名按真实扩展名 .exe 拒绝"""
        with pytest.raises(FileValidationError):
            validate_upload_name("report.pdf.exe")
