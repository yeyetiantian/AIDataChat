"""DuckDB 连接管理（简化版）

只保留 WIDE_DETAIL 宽表库连接。
支持 PyInstaller 打包运行模式。
"""

from __future__ import annotations

import atexit
import os
import sys

import duckdb


def _get_base_dir() -> str:
    """获取 backend 基础目录（源码模式或打包模式）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_backend_dir = _get_base_dir()


def get_wide_db_path() -> str:
    """WIDE_DETAIL 宽表库路径（vcloud_wide.db）"""
    if getattr(sys, "frozen", False):
        default = "vcloud_wide.db"
    else:
        default = "../vcloud_wide.db"
    raw = os.getenv("WIDE_DB_PATH", default).strip()
    if os.path.isabs(raw):
        return raw
    return os.path.abspath(os.path.join(_backend_dir, raw))


WIDE_DB_PATH = get_wide_db_path()
WIDE_DETAIL_NAME = "WIDE_DETAIL"
_CONN: duckdb.DuckDBPyConnection | None = None


def get_conn() -> duckdb.DuckDBPyConnection:
    """获取宽表库连接（vcloud_wide.db，只读单例）"""
    global _CONN
    if _CONN is None:
        _CONN = duckdb.connect(WIDE_DB_PATH, read_only=True)
        _CONN.execute("SET threads TO 2;")
        _CONN.execute("SET memory_limit = '6GB';")
        _CONN.execute("SET preserve_insertion_order = false;")
        _CONN.execute(f"SET temp_directory = '{_backend_dir}/duckdb_temp';")
        atexit.register(_close)
    return _CONN


def wide_detail_exists() -> bool:
    """检测宽表库中 WIDE_DETAIL 表是否存在"""
    try:
        conn = get_conn()
        result = conn.execute(
            f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{WIDE_DETAIL_NAME}' AND table_schema = 'main'"
        ).fetchone()
        return result[0] > 0
    except Exception:
        return False


def get_wide_detail_name() -> str:
    return WIDE_DETAIL_NAME


def _close() -> None:
    global _CONN
    if _CONN is not None:
        try:
            _CONN.close()
        except Exception:
            pass
        _CONN = None
