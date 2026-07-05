"""AIDataChat 启动器

PyInstaller 打包后的生产运行入口。
开发模式也可直接使用：python run.py

自动切换到脚本所在目录，加载 .env，启动 FastAPI + Uvicorn。
"""

from __future__ import annotations

import os
import sys


def _get_base_dir() -> str:
    """获取基础目录（源码或打包模式）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    base_dir = _get_base_dir()
    os.chdir(base_dir)

    # 加载 .env（必须在导入 main 之前执行）
    from dotenv import load_dotenv

    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[AIDataChat] 加载配置: {env_path}")
    else:
        print(f"[AIDataChat] 未找到 .env 文件，使用默认配置")

    # 导入并启动 FastAPI 应用
    from main import app
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    print(f"[AIDataChat] 启动服务 → http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
