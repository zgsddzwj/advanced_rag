"""
项目日志工具类
基于 loguru 实现，支持配置控制台/文件双输出（配置来自统一配置中心 settings）
演进5：日志行自动携带 request_id（来自请求上下文，后台线程中为 "-"），
同一请求的全部日志可通过 request_id 串联检索
"""
import sys
import inspect
from pathlib import Path

from loguru import logger

from app.conf.settings import settings
from app.core.context import get_request_id

# 定义日志路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_NAME = "app_{time:YYYYMMDD}.log"
LOG_FILE_PATH = LOG_DIR / LOG_FILE_NAME

# 定义日志格式（request_id 由 fix_log_position 注入 extra）
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[request_id]}</cyan> | "
    "<cyan>{name: <20}</cyan>:<cyan>{function: <15}</cyan>:<cyan>{line: <4}</cyan> - "
    "<level>{message}</level>"
)


def init_logger():
    """初始化全局日志配置"""
    logger.remove()
    # extra 默认值：未经中间件的日志（启动/后台线程）request_id 显示为 "-"
    logger.configure(extra={"request_id": "-"})

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
    """遍历调用栈，跳过 loguru 内部帧，定位业务代码实际调用位置；同时注入请求上下文"""
    record["extra"]["request_id"] = get_request_id()
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
