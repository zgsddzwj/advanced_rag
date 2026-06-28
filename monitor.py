"""
监控模块 - 用于监控 MinerU PDF 解析过程的性能指标和日志
"""

import time
import logging
import psutil
import os
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime
from tqdm import tqdm
from colorama import Fore, Style, init

# 初始化 colorama（Windows 兼容性）
init(autoreset=True)


class Monitor:
    """监控类，用于追踪 PDF 解析过程的性能指标"""
    
    def __init__(self, log_file: Optional[str] = None, enable_progress: bool = True):
        """
        初始化监控器
        
        Args:
            log_file: 日志文件路径，如果为 None 则不保存日志文件
            enable_progress: 是否启用进度条显示
        """
        self.log_file = log_file
        self.enable_progress = enable_progress
        self.steps_data: Dict[str, Dict[str, Any]] = {}
        self.start_time = None
        self.end_time = None
        self.process = psutil.Process(os.getpid())
        self.initial_memory = self._get_memory_usage()
        self.progress_bar = None
        
        # 设置日志记录器
        self.logger = logging.getLogger('pdf_parser_monitor')
        self.logger.setLevel(logging.INFO)
        
        # 控制台处理器（彩色输出）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器
        if self.log_file:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量（MB）"""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024  # 转换为 MB
        except Exception:
            return 0.0
    
    def start_monitoring(self):
        """开始监控整个解析过程"""
        self.start_time = time.time()
        self.initial_memory = self._get_memory_usage()
        self.logger.info(f"{Fore.CYAN}{'='*60}")
        self.logger.info(f"{Fore.CYAN}开始 PDF 解析监控")
        self.logger.info(f"{Fore.CYAN}{'='*60}")
        
        if self.enable_progress:
            self.progress_bar = tqdm(
                total=4,  # 4 个主要步骤：classify, analyze, parse, markdown
                desc="解析进度",
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                colour='green'
            )
    
    def end_monitoring(self):
        """结束监控"""
        self.end_time = time.time()
        total_time = self.end_time - self.start_time if self.start_time else 0
        final_memory = self._get_memory_usage()
        memory_increase = final_memory - self.initial_memory
        
        if self.progress_bar:
            self.progress_bar.close()
        
        self.logger.info(f"{Fore.CYAN}{'='*60}")
        self.logger.info(f"{Fore.GREEN}解析完成！")
        self.logger.info(f"{Fore.YELLOW}总耗时: {total_time:.2f} 秒")
        self.logger.info(f"{Fore.YELLOW}初始内存: {self.initial_memory:.2f} MB")
        self.logger.info(f"{Fore.YELLOW}最终内存: {final_memory:.2f} MB")
        self.logger.info(f"{Fore.YELLOW}内存增量: {memory_increase:.2f} MB")
        self.logger.info(f"{Fore.CYAN}{'='*60}")
    
    def monitor_step(self, step_name: str, description: str = None):
        """
        装饰器：监控单个解析步骤
        
        Args:
            step_name: 步骤名称（如 'classify', 'analyze', 'parse', 'markdown'）
            description: 步骤描述，用于显示
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                step_desc = description or step_name
                step_start_time = time.time()
                step_start_memory = self._get_memory_usage()
                
                self.logger.info(f"{Fore.BLUE}[{step_name.upper()}] {Fore.WHITE}开始: {step_desc}")
                
                try:
                    # 执行被装饰的函数
                    result = func(*args, **kwargs)
                    
                    step_end_time = time.time()
                    step_end_memory = self._get_memory_usage()
                    step_duration = step_end_time - step_start_time
                    step_memory_increase = step_end_memory - step_start_memory
                    
                    # 记录步骤数据
                    self.steps_data[step_name] = {
                        'step_name': step_name,
                        'description': step_desc,
                        'start_time': datetime.fromtimestamp(step_start_time).isoformat(),
                        'end_time': datetime.fromtimestamp(step_end_time).isoformat(),
                        'duration': step_duration,
                        'start_memory_mb': step_start_memory,
                        'end_memory_mb': step_end_memory,
                        'memory_increase_mb': step_memory_increase,
                        'peak_memory_mb': step_end_memory,
                        'status': 'success',
                        'error': None
                    }
                    
                    # 更新进度条
                    if self.progress_bar:
                        self.progress_bar.update(1)
                        self.progress_bar.set_postfix({'当前步骤': step_name})
                    
                    self.logger.info(
                        f"{Fore.GREEN}[{step_name.upper()}] {Fore.WHITE}完成: "
                        f"{step_desc} - 耗时: {step_duration:.2f}s, "
                        f"内存: {step_start_memory:.2f}MB -> {step_end_memory:.2f}MB "
                        f"(+{step_memory_increase:.2f}MB)"
                    )
                    
                    return result
                    
                except Exception as e:
                    step_end_time = time.time()
                    step_end_memory = self._get_memory_usage()
                    step_duration = step_end_time - step_start_time
                    step_memory_increase = step_end_memory - step_start_memory
                    
                    # 记录错误信息
                    self.steps_data[step_name] = {
                        'step_name': step_name,
                        'description': step_desc,
                        'start_time': datetime.fromtimestamp(step_start_time).isoformat(),
                        'end_time': datetime.fromtimestamp(step_end_time).isoformat(),
                        'duration': step_duration,
                        'start_memory_mb': step_start_memory,
                        'end_memory_mb': step_end_memory,
                        'memory_increase_mb': step_memory_increase,
                        'peak_memory_mb': step_end_memory,
                        'status': 'failed',
                        'error': str(e)
                    }
                    
                    if self.progress_bar:
                        self.progress_bar.update(1)
                    
                    self.logger.error(
                        f"{Fore.RED}[{step_name.upper()}] {Fore.WHITE}失败: "
                        f"{step_desc} - 耗时: {step_duration:.2f}s, "
                        f"错误: {str(e)}"
                    )
                    
                    raise
                    
            return wrapper
        return decorator
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        获取性能报告
        
        Returns:
            包含所有步骤性能指标的字典
        """
        total_time = (self.end_time - self.start_time) if (self.start_time and self.end_time) else 0
        final_memory = self._get_memory_usage()
        memory_increase = final_memory - self.initial_memory
        
        report = {
            'summary': {
                'start_time': datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
                'end_time': datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
                'total_duration_seconds': total_time,
                'initial_memory_mb': self.initial_memory,
                'final_memory_mb': final_memory,
                'total_memory_increase_mb': memory_increase
            },
            'steps': self.steps_data
        }
        
        return report
    
    def print_performance_report(self):
        """打印性能报告到控制台"""
        report = self.get_performance_report()
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}性能报告")
        print(f"{Fore.CYAN}{'='*60}")
        
        summary = report['summary']
        print(f"{Fore.YELLOW}总耗时: {summary['total_duration_seconds']:.2f} 秒")
        print(f"{Fore.YELLOW}内存使用: {summary['initial_memory_mb']:.2f} MB -> "
              f"{summary['final_memory_mb']:.2f} MB (增量: {summary['total_memory_increase_mb']:.2f} MB)")
        
        print(f"\n{Fore.CYAN}各步骤详情:")
        print(f"{Fore.CYAN}{'-'*60}")
        
        for step_name, step_data in report['steps'].items():
            status_color = Fore.GREEN if step_data['status'] == 'success' else Fore.RED
            status_text = "✓ 成功" if step_data['status'] == 'success' else "✗ 失败"
            
            print(f"{status_color}[{step_name.upper()}] {status_text}")
            print(f"  描述: {step_data['description']}")
            print(f"  耗时: {step_data['duration']:.2f} 秒")
            print(f"  内存: {step_data['start_memory_mb']:.2f} MB -> "
                  f"{step_data['end_memory_mb']:.2f} MB (+{step_data['memory_increase_mb']:.2f} MB)")
            
            if step_data['error']:
                print(f"  {Fore.RED}错误: {step_data['error']}")
            print()
        
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

