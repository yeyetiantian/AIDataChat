"""AIDataChat 启动器

PyInstaller 打包后的生产运行入口。
开发模式也可直接使用：python run.py

自动切换到脚本所在目录，加载 .env，启动 FastAPI + Uvicorn，
自动打开浏览器访问前端界面。
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser


def _get_base_dir() -> str:
    """获取基础目录（源码或打包模式）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _open_browser(url: str, delay: float = 1.5) -> None:
    """延迟打开浏览器"""
    import time
    time.sleep(delay)
    print(f"[AIDataChat] 自动打开浏览器: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[AIDataChat] 打开浏览器失败（可手动访问）: {e}")


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

    # 构造浏览器可访问地址
    if host == "0.0.0.0":
        browser_url = f"http://127.0.0.1:{port}"
    else:
        browser_url = f"http://{host}:{port}"

    print(f"[AIDataChat] 启动服务 → {browser_url}")
    print(f"[AIDataChat] 按 Ctrl+C 停止服务")

    # 延迟打开浏览器（不阻塞服务器启动）
    threading.Thread(target=_open_browser, args=(browser_url,), daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
