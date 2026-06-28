"""
项目路径工具
统一管理项目根目录和各类输出目录的路径
"""
from pathlib import Path

# 项目根目录：从当前文件向上回溯到项目根
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
