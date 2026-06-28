"""
配置管理模块
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """项目配置类"""
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.absolute()
    
    # 目录配置
    LOGS_DIR = PROJECT_ROOT / "logs"
    OUTPUT_DIR = PROJECT_ROOT / "output"
    EXAMPLES_DIR = PROJECT_ROOT / "examples"
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # 监控配置
    ENABLE_PROGRESS_BAR = True
    ENABLE_PERFORMANCE_MONITORING = True
    ENABLE_DETAILED_LOGGING = True
    
    # MinerU 配置
    DROP_MODE = "none"  # 可选: "none", "image", "table", "image,table"
    
    @classmethod
    def init_directories(cls):
        """初始化必要的目录"""
        directories = [
            cls.LOGS_DIR,
            cls.OUTPUT_DIR,
            cls.EXAMPLES_DIR
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        return directories
    
    @classmethod
    def get_log_file_path(cls, filename: Optional[str] = None) -> Path:
        """
        获取日志文件路径
        
        Args:
            filename: 日志文件名，如果为 None 则使用时间戳生成
            
        Returns:
            日志文件完整路径
        """
        from datetime import datetime
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pdf_parser_{timestamp}.log"
        
        return cls.LOGS_DIR / filename
    
    @classmethod
    def get_output_dir(cls, subdir: Optional[str] = None) -> Path:
        """
        获取输出目录路径
        
        Args:
            subdir: 子目录名，如果提供则在输出目录下创建子目录
            
        Returns:
            输出目录完整路径
        """
        if subdir:
            output_path = cls.OUTPUT_DIR / subdir
            output_path.mkdir(parents=True, exist_ok=True)
            return output_path
        return cls.OUTPUT_DIR
    
    @classmethod
    def validate_config(cls):
        """验证配置是否有效"""
        errors = []
        
        # 验证日志级别
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if cls.LOG_LEVEL not in valid_log_levels:
            errors.append(f"无效的日志级别: {cls.LOG_LEVEL}，应该是 {valid_log_levels} 之一")
        
        # 验证 drop_mode
        valid_drop_modes = ["none", "image", "table", "image,table"]
        if cls.DROP_MODE not in valid_drop_modes:
            errors.append(f"无效的 drop_mode: {cls.DROP_MODE}，应该是 {valid_drop_modes} 之一")
        
        if errors:
            raise ValueError(f"配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors))
        
        return True

