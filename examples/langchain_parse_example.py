"""
LangChain PDF 解析示例脚本

使用 LangChain 解析 PDF 文件，展示具体的文本内容和结构化信息
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_parser import LangChainPDFParser
from result_viewer import ResultViewer


def main():
    """主函数：使用 LangChain 解析 PDF 文件"""
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: python langchain_parse_example.py <pdf_file_path> [output_dir] [--full-text]")
        print("示例: python langchain_parse_example.py sample.pdf")
        print("      python langchain_parse_example.py sample.pdf ./output")
        print("      python langchain_parse_example.py sample.pdf --full-text")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = None
    show_full_text = False
    
    # 解析参数
    for arg in sys.argv[2:]:
        if arg == "--full-text":
            show_full_text = True
        elif not arg.startswith("--"):
            output_dir = arg
    
    # 检查 PDF 文件是否存在
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"错误: PDF 文件不存在: {pdf_path}")
        sys.exit(1)
    
    print(f"\n开始使用 LangChain 解析 PDF 文件: {pdf_path}")
    if output_dir:
        print(f"输出目录: {output_dir}")
    print()
    
    try:
        # 创建 LangChain PDF 解析器实例
        parser = LangChainPDFParser(
            output_dir=output_dir,
            enable_monitoring=True,  # 启用监控
            enable_progress=True,    # 显示进度条
            use_pymupdf=True        # 使用 PyMuPDF（更快）
        )
        
        # 执行解析
        result = parser.parse_pdf(
            pdf_path=pdf_path,
            output_filename=None,  # 自动生成文件名
            show_preview=True,     # 显示预览
            preview_length=500     # 预览长度
        )
        
        # 检查解析结果
        if result['status'] == 'success':
            print(f"\n✓ 解析成功！")
            
            # 使用结果查看器显示详细结果
            viewer = ResultViewer()
            viewer.display_results(
                result,
                show_full_text=show_full_text,
                show_pages=True,
                max_pages_display=5
            )
            
            # 显示文件路径
            if 'output_files' in result:
                print(f"\n📁 结果文件已保存:")
                for file_type, file_path in result['output_files'].items():
                    print(f"  • {file_type}: {file_path}")
            
            # 显示性能报告
            if result.get('performance_report'):
                report = result['performance_report']
                summary = report.get('summary', {})
                if summary:
                    print(f"\n⏱️  性能指标:")
                    print(f"  • 总耗时: {summary.get('total_duration_seconds', 0):.2f} 秒")
                    print(f"  • 内存增量: {summary.get('total_memory_increase_mb', 0):.2f} MB")
        else:
            print(f"\n✗ 解析失败: {result.get('error', '未知错误')}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

