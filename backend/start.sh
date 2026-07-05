#!/bin/bash
# 后端一键启动脚本
# 用法: ./start-backend.sh

set -e

# 切换到脚本所在目录（backend/）
cd "$(dirname "$0")"

echo "🚀 启动企业级数据透视分析系统后端..."

# 激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ 虚拟环境已激活"
else
    echo "❌ 虚拟环境不存在，请先创建: python3 -m venv .venv"
    exit 1
fi

# 启动 FastAPI 服务
echo "📡 启动 FastAPI (http://localhost:8000)..."
echo "📖 API 文档: http://localhost:8000/docs"
echo ""
python main.py
