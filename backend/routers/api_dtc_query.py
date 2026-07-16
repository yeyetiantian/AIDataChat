"""DTC 数据查询 API — 通过 SQL 查询 dtc_info / dtc_trigger 表"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import sys
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("api_dtc_query")

if getattr(sys, "frozen", False):
    _backend_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(_backend_dir, "ai_data.db")

router = APIRouter(prefix="/api/dtc", tags=["dtc"])

# 仅允许查询这些表
_ALLOWED_TABLES = {"dtc_info", "dtc_trigger"}

# SQL 危险关键字（不允许出现）
_DANGEROUS_KW = [
    "DELETE", "DROP", "INSERT", "UPDATE", "ALTER", "CREATE",
    "PRAGMA", "ATTACH", "DETACH", "REINDEX", "REPLACE", "TRUNCATE",
]


class SqlQueryRequest(BaseModel):
    sql: str = Field(..., min_length=7, description="SELECT 查询语句，仅限查询 dtc_info / dtc_trigger 表")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_sql(sql: str) -> str:
    """校验 SQL：只允许 SELECT，不允许危险操作"""
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="只允许 SELECT 查询")

    upper_sql = stripped.upper()
    for kw in _DANGEROUS_KW:
        if re.search(rf"\b{re.escape(kw)}\b", upper_sql):
            raise HTTPException(status_code=400, detail=f"查询中包含不允许的关键字: {kw}")

    return stripped


@router.post("/query")
async def query_dtc(req: SqlQueryRequest) -> dict[str, Any]:
    """执行 SQL 查询 dtc_info / dtc_trigger 表，返回列名和数据行"""
    sql = _validate_sql(req.sql)
    conn = _get_conn()
    try:
        cursor = conn.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        columns = [desc[0] for desc in cursor.description]
        logger.info("SQL OK (%d rows): %.200s", len(rows), sql)
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "total": len(rows),
        }
    except sqlite3.Error as e:
        logger.warning("SQL ERROR: %s — %.200s", e, sql)
        raise HTTPException(status_code=400, detail=f"SQL 执行错误: {e}")
    finally:
        conn.close()