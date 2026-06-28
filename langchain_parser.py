"""
LangChain PDF 解析器 - 使用 LangChain 解析 PDF 文件，提取文本和结构化信息
集成监控功能，保留性能追踪
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader
from langchain_core.documents import Document

from monitor import Monitor
from config import Config


class LangChainPDFParser:
    """使用 LangChain 解析 PDF 文件的解析器类，集成监控功能"""
    
    def __init__(
        self,
        output_dir: Optional[str] = None,
        enable_monitoring: bool = True,
        log_file: Optional[str] = None,
        enable_progress: bool = True,
        use_pymupdf: bool = True
    ):
        """
        初始化 LangChain PDF 解析器
        
        Args:
            output_dir: 输出目录，如果为 None 则使用配置中的默认目录
            enable_monitoring: 是否启用监控
            log_file: 日志文件路径，如果为 None 则自动生成
            enable_progress: 是否显示进度条
            use_pymupdf: 是否使用 PyMuPDFLoader（更快），False 使用 PyPDFLoader
        """
        # 初始化配置
        Config.init_directories()
        
        # 设置输出目录
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = Config.get_output_dir()
        
        # 创建子目录
        self.text_output_dir = self.output_dir / "text"
        self.structured_output_dir = self.output_dir / "structured"
        self.text_output_dir.mkdir(parents=True, exist_ok=True)
        self.structured_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化监控器
        self.enable_monitoring = enable_monitoring
        if self.enable_monitoring:
            if log_file is None:
                log_file = str(Config.get_log_file_path())
            self.monitor = Monitor(log_file=log_file, enable_progress=enable_progress)
        else:
            self.monitor = None
        
        # 选择加载器
        self.loader_class = PyMuPDFLoader if use_pymupdf else PyPDFLoader
    
    def parse_pdf(
        self,
        pdf_path: str,
        output_filename: Optional[str] = None,
        show_preview: bool = True,
        preview_length: int = 500
    ) -> Dict[str, Any]:
        """
        解析 PDF 文件
        
        Args:
            pdf_path: PDF 文件路径
            output_filename: 输出文件名（不含扩展名），如果为 None 则使用 PDF 文件名
            show_preview: 是否在控制台显示文本预览
            preview_length: 预览文本的长度（字符数）
            
        Returns:
            解析结果字典，包含：
            - text_content: 完整文本内容
            - pages_text: 每页的文本列表
            - metadata: PDF 元数据
            - pages_info: 每页的详细信息
            - stats: 统计信息
            - output_files: 输出文件路径
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
        
        # 开始监控
        if self.monitor:
            self.monitor.start_monitoring()
        
        try:
            # 加载 PDF 文档
            documents = self._load_pdf(pdf_path)
            
            # 提取文本和元数据
            result = self._extract_content(documents, pdf_path)
            
            # 生成输出文件名
            if output_filename is None:
                output_filename = pdf_path.stem
            
            # 保存结果
            output_files = self._save_results(result, output_filename)
            result['output_files'] = output_files
            
            # 显示预览
            if show_preview:
                self._show_preview(result, preview_length)
            
            # 保存性能报告
            performance_report = None
            if self.monitor:
                self.monitor.end_monitoring()
                performance_report = self.monitor.get_performance_report()
                
                # 保存性能报告
                report_filename = f"{output_filename}_performance_report.json"
                report_path = self.structured_output_dir / report_filename
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(performance_report, f, ensure_ascii=False, indent=2)
                
                # 打印性能报告
                self.monitor.print_performance_report()
            
            result['performance_report'] = performance_report
            result['status'] = 'success'
            
            return result
            
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
    
    def _load_pdf(self, pdf_path: Path) -> List[Document]:
        """加载 PDF 文档（包装监控）"""
        if self.monitor:
            @self.monitor.monitor_step('load', '加载 PDF 文件')
            def _execute():
                loader = self.loader_class(str(pdf_path))
                return loader.load()
            return _execute()
        loader = self.loader_class(str(pdf_path))
        return loader.load()
    
    def _extract_content(self, documents: List[Document], pdf_path: Path) -> Dict[str, Any]:
        """提取文本和元数据（包装监控）"""
        if self.monitor:
            @self.monitor.monitor_step('extract', '提取文本内容')
            def _execute():
                return self._do_extract_content(documents, pdf_path)
            return _execute()
        return self._do_extract_content(documents, pdf_path)
    
    def _do_extract_content(self, documents: List[Document], pdf_path: Path) -> Dict[str, Any]:
        """执行内容提取"""
        pages_text = []
        pages_info = []
        full_text = []
        
        for i, doc in enumerate(documents):
            page_num = i + 1
            page_text = doc.page_content
            pages_text.append(page_text)
            full_text.append(page_text)
            
            # 收集页面信息
            page_info = {
                'page_number': page_num,
                'text_length': len(page_text),
                'char_count': len(page_text),
                'word_count': len(page_text.split()) if page_text else 0,
                'line_count': len(page_text.split('\n')) if page_text else 0
            }
            
            # 添加元数据
            if doc.metadata:
                page_info['metadata'] = doc.metadata
            
            pages_info.append(page_info)
        
        # 合并所有文本
        full_text_content = '\n\n'.join(full_text)
        
        # 提取文档元数据
        document_metadata = {}
        if documents and documents[0].metadata:
            document_metadata = documents[0].metadata.copy()
            # 移除页面特定的元数据
            document_metadata.pop('page', None)
            document_metadata.pop('source', None)
        
        # 计算统计信息
        total_chars = len(full_text_content)
        total_words = len(full_text_content.split()) if full_text_content else 0
        total_pages = len(documents)
        
        stats = {
            'total_pages': total_pages,
            'total_characters': total_chars,
            'total_words': total_words,
            'average_chars_per_page': total_chars / total_pages if total_pages > 0 else 0,
            'average_words_per_page': total_words / total_pages if total_pages > 0 else 0,
            'pdf_file': str(pdf_path),
            'parsed_at': datetime.now().isoformat()
        }
        
        return {
            'text_content': full_text_content,
            'pages_text': pages_text,
            'metadata': document_metadata,
            'pages_info': pages_info,
            'stats': stats
        }
    
    def _save_results(self, result: Dict[str, Any], output_filename: str) -> Dict[str, str]:
        """保存解析结果到文件"""
        output_files = {}
        
        # 保存文本文件
        text_file = self.text_output_dir / f"{output_filename}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(result['text_content'])
        output_files['text'] = str(text_file)
        
        # 保存结构化信息（JSON）
        structured_data = {
            'metadata': result['metadata'],
            'pages_info': result['pages_info'],
            'stats': result['stats']
        }
        json_file = self.structured_output_dir / f"{output_filename}_info.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        output_files['json'] = str(json_file)
        
        # 保存每页的文本（可选）
        pages_dir = self.text_output_dir / f"{output_filename}_pages"
        pages_dir.mkdir(exist_ok=True)
        for i, page_text in enumerate(result['pages_text'], 1):
            page_file = pages_dir / f"page_{i:03d}.txt"
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(page_text)
        output_files['pages_dir'] = str(pages_dir)
        
        return output_files
    
    def _show_preview(self, result: Dict[str, Any], preview_length: int = 500):
        """在控制台显示解析结果预览"""
        from colorama import Fore, Style, init
        init(autoreset=True)
        
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}📄 PDF 解析结果预览")
        print(f"{Fore.CYAN}{'='*70}")
        
        # 显示统计信息
        stats = result['stats']
        print(f"\n{Fore.YELLOW}📊 统计信息:")
        print(f"  • 总页数: {stats['total_pages']}")
        print(f"  • 总字符数: {stats['total_characters']:,}")
        print(f"  • 总词数: {stats['total_words']:,}")
        print(f"  • 平均每页字符数: {stats['average_chars_per_page']:.0f}")
        print(f"  • 平均每页词数: {stats['average_words_per_page']:.0f}")
        
        # 显示元数据
        if result['metadata']:
            print(f"\n{Fore.YELLOW}📋 文档元数据:")
            for key, value in result['metadata'].items():
                if value:
                    print(f"  • {key}: {value}")
        
        # 显示文本预览
        text_content = result['text_content']
        if text_content:
            preview = text_content[:preview_length]
            if len(text_content) > preview_length:
                preview += "..."
            
            print(f"\n{Fore.YELLOW}📝 文本内容预览（前 {min(preview_length, len(text_content))} 个字符）:")
            print(f"{Fore.WHITE}{'-'*70}")
            print(preview)
            print(f"{Fore.WHITE}{'-'*70}")
        
        # 显示页面信息
        if result['pages_info']:
            print(f"\n{Fore.YELLOW}📑 页面信息:")
            for page_info in result['pages_info'][:5]:  # 只显示前5页
                print(f"  • 第 {page_info['page_number']} 页: "
                      f"{page_info['char_count']:,} 字符, "
                      f"{page_info['word_count']:,} 词")
            if len(result['pages_info']) > 5:
                print(f"  ... 还有 {len(result['pages_info']) - 5} 页")
        
        # 显示输出文件
        if 'output_files' in result:
            print(f"\n{Fore.GREEN}💾 输出文件:")
            print(f"  • 文本文件: {result['output_files']['text']}")
            print(f"  • JSON 文件: {result['output_files']['json']}")
            print(f"  • 分页文件: {result['output_files']['pages_dir']}")
        
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")

