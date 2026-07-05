"""DuckDB 连接管理

提供读写分离及跨库连接策略：
- 主连接（vcloud_duck.db）：源数据查询（API、Pivot、Detail）
- 宽表连接（vcloud_wide.db）：WIDE_DETAIL 明细宽表（构建 & 健康检查）
"""

from __future__ import annotations

import atexit
import os

import duckdb

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_db_path() -> str:
    """源数据库路径（vcloud_duck.db）

    1. 优先使用环境变量 DB_PATH（.env 中配置）
    2. 相对路径相对于 backend/ 目录解析
    3. 默认 ../vcloud_duck.db
    """
    raw = os.getenv("DB_PATH", "../vcloud_duck.db").strip()
    if os.path.isabs(raw):
        return raw
    return os.path.abspath(os.path.join(_backend_dir, raw))


def get_wide_db_path() -> str:
    """WIDE_DETAIL 宽表独立库路径（vcloud_wide.db）

    1. 优先使用环境变量 WIDE_DB_PATH（.env 中配置）
    2. 默认 ../vcloud_wide.db
    """
    raw = os.getenv("WIDE_DB_PATH", "../vcloud_wide.db").strip()
    if os.path.isabs(raw):
        return raw
    return os.path.abspath(os.path.join(_backend_dir, raw))


DB_PATH = get_db_path()
WIDE_DB_PATH = get_wide_db_path()
_MAIN_CONN: duckdb.DuckDBPyConnection | None = None
_WIDE_CONN: duckdb.DuckDBPyConnection | None = None

WIDE_DETAIL_NAME = "WIDE_DETAIL"           # 明细宽表


def get_conn() -> duckdb.DuckDBPyConnection:
    """获取源库连接（vcloud_duck.db），自动 ATTACH 宽表库以便直接查询 WIDE_DETAIL"""
    global _MAIN_CONN
    if _MAIN_CONN is None:
        _MAIN_CONN = duckdb.connect(DB_PATH)
        _MAIN_CONN.execute("SET threads TO 2;")
        _MAIN_CONN.execute("SET memory_limit = '6GB';")
        _MAIN_CONN.execute("SET preserve_insertion_order = false;")
        _MAIN_CONN.execute(f"SET temp_directory = '{_backend_dir}/duckdb_temp';")
        # ATTACH 宽表库（只读），使 WIDE_DETAIL 可在主连接中直接查询
        try:
            if os.path.exists(WIDE_DB_PATH):
                _MAIN_CONN.execute(f"ATTACH '{WIDE_DB_PATH}' AS wide_db (READ_ONLY);")
        except Exception:
            pass  # 宽表未就绪时忽略，fallback 到 CTE 构建
        atexit.register(_close)
    return _MAIN_CONN


def get_write_conn() -> duckdb.DuckDBPyConnection:
    """获取源库写连接（后台构表用，每次新创建）"""
    conn = duckdb.connect(DB_PATH)
    conn.execute("SET threads TO 2;")
    conn.execute("SET memory_limit = '6GB';")
    conn.execute("SET preserve_insertion_order = false;")
    conn.execute(f"SET temp_directory = '{_backend_dir}/duckdb_temp';")
    return conn


def get_wide_conn() -> duckdb.DuckDBPyConnection:
    """获取宽表库连接（vcloud_wide.db，只读，单例）"""
    global _WIDE_CONN
    if _WIDE_CONN is None:
        _WIDE_CONN = duckdb.connect(WIDE_DB_PATH, read_only=True)
        _WIDE_CONN.execute("SET threads TO 2;")
        _WIDE_CONN.execute("SET memory_limit = '6GB';")
        _WIDE_CONN.execute("SET preserve_insertion_order = false;")
        _WIDE_CONN.execute(f"SET temp_directory = '{_backend_dir}/duckdb_temp';")
        atexit.register(_close_wide)
    return _WIDE_CONN


def wide_detail_exists() -> bool:
    """检测宽表库中 WIDE_DETAIL 表是否存在"""
    try:
        conn = get_wide_conn()
        result = conn.execute(
            f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{WIDE_DETAIL_NAME}' AND table_schema = 'main'"
        ).fetchone()
        return result[0] > 0
    except Exception:
        return False


def get_wide_detail_name() -> str:
    """获取明细宽表名（WIDE_DETAIL）"""
    return WIDE_DETAIL_NAME


def _close() -> None:
    global _MAIN_CONN
    if _MAIN_CONN is not None:
        try:
            _MAIN_CONN.close()
        except Exception:
            pass
        _MAIN_CONN = None


def _close_wide() -> None:
    global _WIDE_CONN
    if _WIDE_CONN is not None:
        try:
            _WIDE_CONN.close()
        except Exception:
            pass
        _WIDE_CONN = None
