#!/usr/bin/env python3
"""AIDataChat 跨平台打包脚本

将后端 FastAPI + 前端 Vue 打包为单个可执行目录。
用法:  python build_package.py

依赖: pip install pyinstaller
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BUILD_DIR = BACKEND_DIR / "build_temp"
SPEC_DIR = BACKEND_DIR
OUTPUT_DIR = BACKEND_DIR / "package_output"
FRONTEND_DIST = FRONTEND_DIR / "dist"

# 需要显式收集的包（含二进制扩展或动态导入）
COLLECT_ALL = [
    "duckdb",
    "httpx",
    "openai",
    "tiktoken",
    "yaml",
    "multipart",
    "sniffio",
    "anyio",
    "h11",
    "httpcore",
]

# 隐式导入（PyInstaller 无法自动发现的模块）
HIDDEN_IMPORTS = [
    # Uvicorn 子模块
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.middleware.asgi2",
    "uvicorn.middleware.wsgi",
    # LangGraph
    "langgraph.checkpoint.memory",
    "langgraph.checkpoint",
    "langgraph.constants",
    "langgraph.pregel",
    "langgraph.pregel.read",
    "langgraph.pregel.write",
    # LangChain
    "langchain_core",
    "langchain_core.prompts",
    "langchain_core.messages",
    "langchain_core.output_parsers",
    "langchain_core.language_models",
    "langchain_core.tracers",
    "langchain_openai",
    "langchain_openai.chat_models",
    "langchain.load",
    "langchain.schema",
    "langchain_community",
    # Pydantic
    "pydantic",
    "pydantic.deprecated",
    "pydantic_core",
    # Starlette / FastAPI
    "starlette.staticfiles",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "fastapi.routing",
    # 其他
    "dotenv",
    "pkg_resources",
    "importlib.metadata",
]


def build_frontend() -> None:
    """构建前端并复制到 backend/dist"""
    print("[build] >>> 构建前端...")
    subprocess.run(["npm", "install", "--no-audit", "--no-fund"],
                   cwd=FRONTEND_DIR, check=True, capture_output=True)
    subprocess.run(["npm", "run", "build"],
                   cwd=FRONTEND_DIR, check=True, capture_output=True)

    if not FRONTEND_DIST.is_dir():
        print("[build] 错误: 前端构建失败，未生成 dist 目录")
        sys.exit(1)

    # 复制到 backend/dist（适配 PyInstaller --add-data 相对路径）
    target = BACKEND_DIR / "dist"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FRONTEND_DIST, target)
    print(f"[build] 前端构建完成: {target} ({sum(f.stat().st_size for f in target.rglob('*')) / 1024:.0f} KB)")


def run_pyinstaller() -> None:
    """执行 PyInstaller 打包"""
    print("[build] >>> 执行 PyInstaller 打包...")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--name", "AIDataChat",
        "--distpath", str(OUTPUT_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(SPEC_DIR),
        "--noconfirm",
    ]

    # --collect-all
    for pkg in COLLECT_ALL:
        cmd.append("--collect-all")
        cmd.append(pkg)

    # --hidden-import
    for imp in HIDDEN_IMPORTS:
        cmd.append("--hidden-import")
        cmd.append(imp)

    # --add-data: data 目录（wide_fields.json, charts.json）
    cmd.append("--add-data")
    cmd.append(f"data{os.pathsep}data")

    # --add-data: 前端 dist
    cmd.append("--add-data")
    cmd.append(f"dist{os.pathsep}dist")

    cmd.append(str(BACKEND_DIR / "run.py"))

    print(f"[build] PyInstaller 命令: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=BACKEND_DIR, check=True)
    print(f"[build] PyInstaller 打包完成")


def create_archive() -> str:
    """创建发布压缩包"""
    platform_tag = {
        "win32": "windows",
        "darwin": "macos",
    }.get(sys.platform, "linux")

    arch = {
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(os.uname().machine if hasattr(os, "uname") else "", "x64")

    dist_dir = OUTPUT_DIR / "AIDataChat"
    if not dist_dir.exists():
        # 尝试找其他目录
        for d in OUTPUT_DIR.iterdir():
            if d.is_dir():
                dist_dir = d
                break

    version = os.getenv("RELEASE_VERSION", "1.0.0")
    archive_name = f"AIDataChat-{version}-{platform_tag}-{arch}"

    if sys.platform == "win32":
        archive_path = OUTPUT_DIR / f"{archive_name}.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in dist_dir.rglob("*"):
                zf.write(f, f"{archive_name}/{f.relative_to(dist_dir.parent)}")
    else:
        archive_path = OUTPUT_DIR / f"{archive_name}.tar.gz"
        import tarfile
        with tarfile.open(archive_path, "w:gz") as tf:
            for f in dist_dir.rglob("*"):
                tf.add(f, f"{archive_name}/{f.relative_to(dist_dir.parent)}")

    print(f"[build] 压缩包: {archive_path}")
    return str(archive_path)


def clean() -> None:
    """清理临时文件"""
    print("[build] >>> 清理临时文件...")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(BACKEND_DIR / "dist", ignore_errors=True)
    spec_file = BACKEND_DIR / "AIDataChat.spec"
    if spec_file.exists():
        spec_file.unlink()
    print("[build] 清理完成")


def main() -> None:
    print("=" * 50)
    print("AIDataChat 打包工具")
    print("=" * 50)

    try:
        build_frontend()
        run_pyinstaller()
        archive = create_archive()
        print(f"\n[build] ✅ 打包成功: {archive}")
    except subprocess.CalledProcessError as e:
        print(f"[build] ❌ 打包失败: {e}")
        sys.exit(1)
    finally:
        clean()


if __name__ == "__main__":
    main()
