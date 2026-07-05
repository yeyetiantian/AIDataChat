#!/bin/bash
# 一键启动前后端
# 用法: ./start.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  企业级数据透视分析系统 - 一键启动"
echo "=========================================="

# 启动后端（后台运行）
echo ""
echo "📡 启动后端 (port 8000)..."
cd "$ROOT_DIR/backend"
if [ -f "start.sh" ]; then
    bash start.sh &
    BACKEND_PID=$!
    echo "   后端 PID: $BACKEND_PID"
else
    echo "❌ backend/start.sh 不存在"
    exit 1
fi

# 等待后端就绪
sleep 3

# 启动前端（后台运行）
echo "📡 启动前端 (port 5173)..."
cd "$ROOT_DIR/frontend"
if [ -f "start.sh" ]; then
    bash start.sh &
    FRONTEND_PID=$!
    echo "   前端 PID: $FRONTEND_PID"
else
    echo "❌ frontend/start.sh 不存在"
    exit 1
fi

echo ""
echo "=========================================="
echo "  ✅ 启动完成"
echo "  前端: http://localhost:5173"
echo "  后端: http://localhost:8000"
echo "  API 文档: http://localhost:8000/docs"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待子进程
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
