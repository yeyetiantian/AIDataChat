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
    _npm = ["npm", "install", "--no-audit", "--no-fund"]
    subprocess.run(_npm, cwd=FRONTEND_DIR, check=True, shell=sys.platform == "win32")
    _build = ["npm", "run", "build"]
    subprocess.run(_build, cwd=FRONTEND_DIR, check=True, shell=sys.platform == "win32")

    if not FRONTEND_DIST.is_dir():
        print("[build] 错误: 前端构建失败，未生成 dist 目录")
        sys.exit(1)

    # 复制到 backend/dist（适配 PyInstaller --add-data 相对路径）
    target = BACKEND_DIR / "dist"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FRONTEND_DIST, target)
    print(f"[build] 前端构建完成: {target} ({sum(f.stat().st_size for f in target.rglob('*')) / 1024:.0f} KB)")


def _ensure_data_dir() -> None:
    """确保 data/ 目录存在，创建默认数据文件（data/ 在 .gitignore 中）"""
    data_dir = BACKEND_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # charts.json：看板数据存储
    charts_file = data_dir / "charts.json"
    if not charts_file.exists():
        charts_file.write_text("[]", encoding="utf-8")
        print(f"[build] 创建默认 {charts_file}")

    # wide_fields.json：字段注册表缓存
    fields_file = data_dir / "wide_fields.json"
    if not fields_file.exists():
        import json as _json
        from core.field_registry import WIDE_DETAIL_FIXED_FIELDS
        default_fields = [f.model_dump() for f in WIDE_DETAIL_FIXED_FIELDS]
        fields_file.write_text(_json.dumps(default_fields, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[build] 创建默认 {fields_file}（12 个固定字段）")


def run_pyinstaller() -> None:
    """执行 PyInstaller 打包"""
    print("[build] >>> 执行 PyInstaller 打包...")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    _ensure_data_dir()

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
    result = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print("[build] ❌ PyInstaller 失败，stderr:")
        print(result.stderr[-3000:] if result.stderr else "(无 stderr)")
        print("[build] ❌ 最后 30 行 stdout:")
        lines = (result.stdout or "").splitlines()
        print("\n".join(lines[-30:]))
        result.check_returncode()
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
