"""
项目日志工具类
基于 loguru 实现，支持配置控制台/文件双输出（配置来自统一配置中心 settings）
"""
import sys
import inspect
from pathlib import Path

from loguru import logger

from app.conf.settings import settings

# 定义日志路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_NAME = "app_{time:YYYYMMDD}.log"
LOG_FILE_PATH = LOG_DIR / LOG_FILE_NAME

# 定义日志格式
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name: <20}</cyan>:<cyan>{function: <15}</cyan>:<cyan>{line: <4}</cyan> - "
    "<level>{message}</level>"
)


def init_logger():
    """初始化全局日志配置"""
    logger.remove()

    if settings.log_console_enable:
        logger.add(
            sink=sys.stdout,
            level=settings.log_console_level,
            format=LOG_FORMAT,
            colorize=True,
            enqueue=True
        )

    if settings.log_file_enable:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.add(
            sink=LOG_FILE_PATH,
            level=settings.log_file_level,
            format=LOG_FORMAT,
            rotation="00:00",
            retention=settings.log_file_retention,
            encoding=settings.log_file_encoding,
            enqueue=True,
            backtrace=True,
            diagnose=True
        )

    return logger


# 初始化日志
base_logger = init_logger()


def fix_log_position(record):
    """遍历调用栈，跳过 loguru 内部帧，定位业务代码实际调用位置"""
    for frame in inspect.stack():
        if ("_logger.py" in frame.filename or frame.function == "_log") or "logger.py" in frame.filename:
            continue
        record.update(
            name=frame.filename.split("/")[-1].split("\\")[-1],
            function=frame.function,
            line=frame.lineno
        )
        break


# 应用位置修复，导出全局 logger
logger = base_logger.patch(fix_log_position)
