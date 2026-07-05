#!/bin/bash
# 前端一键启动脚本
# 用法: ./start-frontend.sh

set -e

cd "$(dirname "$0")"

echo "🚀 启动前端开发服务器..."

if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
fi

echo "📡 启动 Vite (http://localhost:5173)..."
npx vite --host
