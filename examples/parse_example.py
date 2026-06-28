"""
MinerU PDF 解析示例脚本

这个示例展示了如何使用 PDFParser 来解析 PDF 文件并监控解析过程。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pdf_parser import PDFParser


def main():
    """主函数：解析 PDF 文件示例"""
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: python parse_example.py <pdf_file_path> [output_dir]")
        print("示例: python parse_example.py sample.pdf")
        print("      python parse_example.py sample.pdf ./output")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 检查 PDF 文件是否存在
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"错误: PDF 文件不存在: {pdf_path}")
        sys.exit(1)
    
    print(f"\n开始解析 PDF 文件: {pdf_path}")
    print(f"输出目录: {output_dir or '默认目录 (output/)'}\n")
    
    try:
        # 创建 PDF 解析器实例
        parser = PDFParser(
            output_dir=output_dir,
            enable_monitoring=True,  # 启用监控
            enable_progress=True     # 显示进度条
        )
        
        # 执行解析
        result = parser.parse_pdf(
            pdf_path=pdf_path,
            output_filename=None,  # 自动生成文件名
            drop_mode=None         # 使用默认配置
        )
        
        # 检查解析结果
        if result['status'] == 'success':
            print(f"\n✓ 解析成功！")
            print(f"  输出文件: {result['output_path']}")
            
            if result.get('performance_report'):
                report = result['performance_report']
                summary = report['summary']
                print(f"  总耗时: {summary['total_duration_seconds']:.2f} 秒")
                print(f"  内存增量: {summary['total_memory_increase_mb']:.2f} MB")
                
                # 显示各步骤耗时
                print(f"\n各步骤耗时:")
                for step_name, step_data in report['steps'].items():
                    print(f"  - {step_data['description']}: {step_data['duration']:.2f}s")
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

