"""
PDF 解析器 - 使用 MinerU (magic-pdf) 解析 PDF 文件，集成监控功能
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.config.make_content_config import DropMode
from magic_pdf.data.data_reader_writer import FileBasedDataWriter

from monitor import Monitor
from config import Config


class PDFParser:
    """PDF 解析器类，集成 MinerU 和监控功能"""
    
    def __init__(
        self,
        output_dir: Optional[str] = None,
        enable_monitoring: bool = True,
        log_file: Optional[str] = None,
        enable_progress: bool = True
    ):
        """
        初始化 PDF 解析器
        
        Args:
            output_dir: 输出目录，如果为 None 则使用配置中的默认目录
            enable_monitoring: 是否启用监控
            log_file: 日志文件路径，如果为 None 则自动生成
            enable_progress: 是否显示进度条
        """
        # 初始化配置
        Config.init_directories()
        
        # 设置输出目录
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = Config.get_output_dir()
        
        # 初始化监控器
        self.enable_monitoring = enable_monitoring
        if self.enable_monitoring:
            if log_file is None:
                log_file = str(Config.get_log_file_path())
            self.monitor = Monitor(log_file=log_file, enable_progress=enable_progress)
        else:
            self.monitor = None
    
    def parse_pdf(
        self,
        pdf_path: str,
        output_filename: Optional[str] = None,
        drop_mode: Optional[str] = None,
        lang: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        解析 PDF 文件
        
        Args:
            pdf_path: PDF 文件路径
            output_filename: 输出 Markdown 文件名，如果为 None 则使用 PDF 文件名
            drop_mode: 丢弃模式，如果为 None 则使用配置中的默认值（"none"）
            lang: 语言代码（可选），用于提高 OCR 准确率
            
        Returns:
            解析结果字典，包含：
            - markdown_content: Markdown 内容
            - output_path: 输出文件路径
            - performance_report: 性能报告（如果启用监控）
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
        
        # 使用配置的 drop_mode 或传入的参数
        drop_mode_str = drop_mode or Config.DROP_MODE
        drop_mode_enum = DropMode.NONE if drop_mode_str == "none" else DropMode(drop_mode_str)
        
        # 开始监控
        if self.monitor:
            self.monitor.start_monitoring()
        
        try:
            # 读取 PDF 文件
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            
            # 创建数据集
            dataset = self._create_dataset(pdf_bytes, lang)
            
            # 执行解析步骤（使用监控装饰器包装）
            infer_result = self._analyze_document(dataset)
            
            # 根据文档类型选择解析模式
            parse_method = dataset.classify()
            
            if parse_method == SupportedPdfParseMethod.TXT:
                pipe_result = self._pipe_txt_mode(infer_result)
            else:
                pipe_result = self._pipe_ocr_mode(infer_result)
            
            # 生成 Markdown
            if output_filename is None:
                output_filename = pdf_path.stem + ".md"
            
            markdown_content = self._generate_markdown(pipe_result, output_filename, drop_mode_enum)
            
            # 保存 Markdown 文件
            output_path = self.output_dir / output_filename
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 保存性能报告
            performance_report = None
            if self.monitor:
                self.monitor.end_monitoring()
                performance_report = self.monitor.get_performance_report()
                
                # 保存性能报告到 JSON 文件
                report_filename = output_filename.replace('.md', '_performance_report.json')
                report_path = self.output_dir / report_filename
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(performance_report, f, ensure_ascii=False, indent=2)
                
                # 打印性能报告
                self.monitor.print_performance_report()
            
            return {
                'markdown_content': markdown_content,
                'output_path': str(output_path),
                'performance_report': performance_report,
                'status': 'success'
            }
            
        except Exception as e:
            if self.monitor:
                self.monitor.end_monitoring()
                error_report = self.monitor.get_performance_report() if self.monitor else None
            else:
                error_report = None
            
            return {
                'status': 'failed',
                'error': str(e),
                'performance_report': error_report
            }
    
    def _create_dataset(self, pdf_bytes: bytes, lang: Optional[str] = None):
        """创建数据集（包装监控）"""
        if self.monitor:
            @self.monitor.monitor_step('classify', '文档分类与数据集创建')
            def _execute():
                return PymuDocDataset(pdf_bytes, lang=lang)
            return _execute()
        return PymuDocDataset(pdf_bytes, lang=lang)
    
    def _analyze_document(self, dataset):
        """文档分析步骤（包装监控）"""
        if self.monitor:
            @self.monitor.monitor_step('analyze', '布局分析')
            def _execute():
                return dataset.apply(
                    doc_analyze,
                    ocr=False,  # 先尝试非 OCR，后续会根据分类结果调整
                    lang=dataset._lang,
                    layout_model=None,
                    formula_enable=None,  # 使用 None 让系统根据配置决定
                    table_enable=None,    # 使用 None 让系统根据配置决定
                )
            return _execute()
        return dataset.apply(
            doc_analyze,
            ocr=False,
            lang=dataset._lang,
            layout_model=None,
            formula_enable=None,  # 使用 None 让系统根据配置决定
            table_enable=None,    # 使用 None 让系统根据配置决定
        )
    
    def _pipe_txt_mode(self, infer_result):
        """文本模式解析（包装监控）"""
        if self.monitor:
            @self.monitor.monitor_step('parse', '内容解析（文本模式）')
            def _execute():
                image_writer = FileBasedDataWriter(str(self.output_dir / "images"))
                return infer_result.pipe_txt_mode(image_writer, debug_mode=True, lang=infer_result.dataset._lang)
            return _execute()
        image_writer = FileBasedDataWriter(str(self.output_dir / "images"))
        return infer_result.pipe_txt_mode(image_writer, debug_mode=True, lang=infer_result.dataset._lang)
    
    def _pipe_ocr_mode(self, infer_result):
        """OCR 模式解析（包装监控）"""
        if self.monitor:
            @self.monitor.monitor_step('parse', '内容解析（OCR 模式）')
            def _execute():
                image_writer = FileBasedDataWriter(str(self.output_dir / "images"))
                return infer_result.pipe_ocr_mode(image_writer, debug_mode=True, lang=infer_result.dataset._lang)
            return _execute()
        image_writer = FileBasedDataWriter(str(self.output_dir / "images"))
        return infer_result.pipe_ocr_mode(image_writer, debug_mode=True, lang=infer_result.dataset._lang)
    
    def _generate_markdown(self, pipe_result, output_filename: str, drop_mode):
        """生成 Markdown 步骤（包装监控）"""
        if self.monitor:
            @self.monitor.monitor_step('markdown', '生成 Markdown')
            def _execute():
                md_writer = FileBasedDataWriter(str(self.output_dir))
                image_dir = "images"
                pipe_result.dump_md(
                    md_writer,
                    output_filename,
                    image_dir,
                    drop_mode=drop_mode,
                )
                # 读取生成的 Markdown 内容
                md_path = self.output_dir / output_filename
                if md_path.exists():
                    with open(md_path, 'r', encoding='utf-8') as f:
                        return f.read()
                return ""
            return _execute()
        
        md_writer = FileBasedDataWriter(str(self.output_dir))
        image_dir = "images"
        pipe_result.dump_md(
            md_writer,
            output_filename,
            image_dir,
            drop_mode=drop_mode,
        )
        # 读取生成的 Markdown 内容
        md_path = self.output_dir / output_filename
        if md_path.exists():
            with open(md_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
