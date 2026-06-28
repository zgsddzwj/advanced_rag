#!/bin/bash
# 启动 Admin 后台服务器

echo "=========================================="
echo "🚀 启动 PDF 解析 Admin 后台"
echo "=========================================="
echo ""

# 激活 conda 环境
source $(conda info --base)/etc/profile.d/conda.sh
conda activate mineru_env

# 启动 Flask 服务器
cd "$(dirname "$0")"
python app.py

