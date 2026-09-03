"""
pytest 全局配置
backend/ 目录加入 sys.path，使测试可以直接导入 app 包
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
