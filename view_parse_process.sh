#!/bin/bash
# 查看 PDF 解析过程的便捷脚本

echo "========================================="
echo "📊 PDF 解析过程查看工具"
echo "========================================="
echo ""

# 查找最新的日志文件
LATEST_LOG=$(ls -t logs/*.log 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
    echo "⚠️  未找到日志文件"
    echo "   请先运行解析: python examples/parse_example.py examples/Sample1.pdf"
    exit 1
fi

echo "📁 最新日志文件: $LATEST_LOG"
echo ""

# 显示解析过程的各个步骤
echo "🔍 解析过程步骤："
echo "----------------------------------------"
grep -E "\[CLASSIFY\]|\[ANALYZE\]|\[PARSE\]|\[MARKDOWN\]|开始|完成|失败" "$LATEST_LOG" | sed 's/.*\[36m//g' | sed 's/\[.*m//g' | head -20
echo ""

# 显示性能统计
echo "📊 性能统计："
echo "----------------------------------------"
grep -E "总耗时|初始内存|最终内存|内存增量" "$LATEST_LOG" | sed 's/.*\[33m//g' | sed 's/\[.*m//g'
echo ""

# 显示错误信息（如果有）
ERRORS=$(grep ERROR "$LATEST_LOG")
if [ ! -z "$ERRORS" ]; then
    echo "⚠️  错误信息："
    echo "----------------------------------------"
    echo "$ERRORS" | sed 's/.*ERROR.*\[31m//g' | sed 's/\[.*m//g' | tail -3
    echo ""
fi

echo "========================================="
echo "💡 提示："
echo "  - 查看完整日志: cat $LATEST_LOG"
echo "  - 实时跟踪: tail -f $LATEST_LOG"
echo "  - 查看所有日志: ls -lht logs/*.log"
echo "========================================="

