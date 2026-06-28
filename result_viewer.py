"""
结果查看器 - 美化展示 PDF 解析结果
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from colorama import Fore, Style, init

init(autoreset=True)


class ResultViewer:
    """解析结果查看器，用于格式化展示 PDF 解析结果"""
    
    def __init__(self):
        """初始化结果查看器"""
        pass
    
    def display_results(
        self,
        result: Dict[str, Any],
        show_full_text: bool = False,
        show_pages: bool = True,
        max_pages_display: int = 5
    ):
        """
        显示解析结果
        
        Args:
            result: 解析结果字典
            show_full_text: 是否显示完整文本（如果为 False，只显示预览）
            show_pages: 是否显示每页信息
            max_pages_display: 最多显示的页数
        """
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}📄 PDF 解析结果")
        print(f"{Fore.CYAN}{'='*70}\n")
        
        # 显示状态
        status = result.get('status', 'unknown')
        if status == 'success':
            print(f"{Fore.GREEN}✓ 解析成功！\n")
        elif status == 'failed':
            print(f"{Fore.RED}✗ 解析失败: {result.get('error', '未知错误')}\n")
            return
        
        # 显示统计信息
        if 'stats' in result:
            self._display_stats(result['stats'])
        
        # 显示元数据
        if 'metadata' in result and result['metadata']:
            self._display_metadata(result['metadata'])
        
        # 显示文本内容
        if 'text_content' in result:
            self._display_text_content(
                result['text_content'],
                show_full=show_full_text,
                title="完整文本内容"
            )
        
        # 显示页面信息
        if show_pages and 'pages_info' in result:
            self._display_pages_info(
                result['pages_info'],
                result.get('pages_text', []),
                max_display=max_pages_display
            )
        
        # 显示输出文件
        if 'output_files' in result:
            self._display_output_files(result['output_files'])
        
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    
    def _display_stats(self, stats: Dict[str, Any]):
        """显示统计信息"""
        print(f"{Fore.YELLOW}📊 统计信息:")
        print(f"  • 总页数: {Fore.WHITE}{stats.get('total_pages', 0)}")
        print(f"  • 总字符数: {Fore.WHITE}{stats.get('total_characters', 0):,}")
        print(f"  • 总词数: {Fore.WHITE}{stats.get('total_words', 0):,}")
        if stats.get('total_pages', 0) > 0:
            print(f"  • 平均每页字符数: {Fore.WHITE}{stats.get('average_chars_per_page', 0):.0f}")
            print(f"  • 平均每页词数: {Fore.WHITE}{stats.get('average_words_per_page', 0):.0f}")
        if 'parsed_at' in stats:
            print(f"  • 解析时间: {Fore.WHITE}{stats['parsed_at']}")
        print()
    
    def _display_metadata(self, metadata: Dict[str, Any]):
        """显示元数据"""
        print(f"{Fore.YELLOW}📋 文档元数据:")
        for key, value in metadata.items():
            if value:
                display_key = key.replace('_', ' ').title()
                print(f"  • {display_key}: {Fore.WHITE}{value}")
        print()
    
    def _display_text_content(
        self,
        text_content: str,
        show_full: bool = False,
        preview_length: int = 500,
        title: str = "文本内容"
    ):
        """显示文本内容"""
        if not text_content:
            print(f"{Fore.YELLOW}📝 {title}: {Fore.WHITE}(空)")
            print()
            return
        
        if show_full:
            print(f"{Fore.YELLOW}📝 {title}:")
            print(f"{Fore.WHITE}{'-'*70}")
            print(text_content)
            print(f"{Fore.WHITE}{'-'*70}\n")
        else:
            preview = text_content[:preview_length]
            if len(text_content) > preview_length:
                preview += f"{Fore.CYAN}... (还有 {len(text_content) - preview_length:,} 个字符)"
            
            print(f"{Fore.YELLOW}📝 {title}预览（前 {min(preview_length, len(text_content)):,} 个字符）:")
            print(f"{Fore.WHITE}{'-'*70}")
            print(preview)
            print(f"{Fore.WHITE}{'-'*70}")
            print(f"{Fore.CYAN}💡 提示: 完整文本已保存到输出文件\n")
    
    def _display_pages_info(
        self,
        pages_info: list,
        pages_text: list,
        max_display: int = 5
    ):
        """显示页面信息"""
        if not pages_info:
            return
        
        print(f"{Fore.YELLOW}📑 页面详情（显示前 {min(max_display, len(pages_info))} 页）:")
        
        for i, (page_info, page_text) in enumerate(zip(pages_info[:max_display], pages_text[:max_display])):
            page_num = page_info.get('page_number', i + 1)
            char_count = page_info.get('char_count', 0)
            word_count = page_info.get('word_count', 0)
            
            print(f"\n  {Fore.CYAN}第 {page_num} 页:")
            print(f"    • 字符数: {Fore.WHITE}{char_count:,}")
            print(f"    • 词数: {Fore.WHITE}{word_count:,}")
            
            # 显示页面文本预览
            if page_text:
                preview = page_text[:200].replace('\n', ' ')
                if len(page_text) > 200:
                    preview += "..."
                print(f"    • 内容预览: {Fore.WHITE}{preview}")
        
        if len(pages_info) > max_display:
            print(f"\n  {Fore.CYAN}... 还有 {len(pages_info) - max_display} 页")
        print()
    
    def _display_output_files(self, output_files: Dict[str, str]):
        """显示输出文件路径"""
        print(f"{Fore.GREEN}💾 输出文件:")
        for file_type, file_path in output_files.items():
            display_type = file_type.replace('_', ' ').title()
            print(f"  • {display_type}: {Fore.WHITE}{file_path}")
        print()
    
    @staticmethod
    def load_and_display_from_file(json_file: str):
        """
        从 JSON 文件加载结果并显示
        
        Args:
            json_file: JSON 文件路径
        """
        json_path = Path(json_file)
        if not json_path.exists():
            print(f"{Fore.RED}错误: 文件不存在 {json_file}")
            return
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 尝试加载文本文件
        text_file = json_path.parent.parent / "text" / json_path.stem.replace("_info", "") / f"{json_path.stem.replace('_info', '')}.txt"
        if not text_file.exists():
            text_file = json_path.parent.parent / "text" / f"{json_path.stem.replace('_info', '')}.txt"
        
        if text_file.exists():
            with open(text_file, 'r', encoding='utf-8') as f:
                data['text_content'] = f.read()
        
        viewer = ResultViewer()
        viewer.display_results(data, show_full_text=False)

