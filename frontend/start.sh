#!/bin/bash
# 前端一键启动脚本
# 用法: ./start.sh

set -e

cd "$(dirname "$0")"

echo "🚀 启动前端开发服务器..."

NODE_VERSION="$(node -v 2>/dev/null || true)"
if [ -z "$NODE_VERSION" ]; then
    echo "❌ 未检测到 Node.js，请先安装 Node.js。"
    exit 1
fi

if ! node -e "const [major, minor] = process.versions.node.split('.').map(Number); process.exit(major > 20 || (major === 20 && minor >= 19) || major >= 22 ? 0 : 1)"; then
    echo "❌ 当前 Node.js 版本为 $NODE_VERSION"
    echo "Vite 8 需要 Node.js >= 20.19 或 >= 22.12"
    echo "请先升级 Node.js，再重新执行前端启动。"
    exit 1
fi

if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
fi

echo "📡 启动 Vite (http://localhost:5173)..."
npm run dev -- --host
