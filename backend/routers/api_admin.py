"""WIDE_DETAIL 宽表 + 字段 / Schema / 管理接口

管理接口：
- POST /api/admin/refresh_wide_detail — 手动触发 WIDE_DETAIL 重建
- GET /api/admin/health — 健康检查
- GET /api/fields — 明细宽表字段列表（供前端拖拽）
- GET /api/schema — WIDE_DETAIL Schema Markdown（供 Agent 或调试使用）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from core.field_registry import get_fields_grouped, get_schema_markdown
from core.db_initializer import build_wide_table, wide_detail_table_exists

logger = logging.getLogger("api_admin")

router = APIRouter(tags=["admin"])


class RefreshResponse(BaseModel):
    success: bool
    message: str
    table_exists: bool = False


@router.get("/api/fields")
async def get_fields():
    """获取明细宽表 WIDE_DETAIL 字段列表（固定 8 字段 + 实时 TOP-N 动态信号列）"""
    return get_fields_grouped(include_wide_detail=True, wide_top_signals=200)


@router.get("/api/schema")
async def get_schema():
    """获取明细宽表 WIDE_DETAIL Schema Markdown"""
    return {"schema": get_schema_markdown(top_signals=60)}


@router.post("/api/admin/refresh_wide_detail")
async def refresh_wide_detail():
    """手动触发 WIDE_DETAIL 明细宽表重建（DROP + CREATE + INSERT）"""
    try:
        ok = build_wide_table()
        exists = wide_detail_table_exists()
        if ok:
            return RefreshResponse(success=True, message="WIDE_DETAIL 明细宽表重建成功", table_exists=exists)
        return RefreshResponse(success=False, message="WIDE_DETAIL 明细宽表重建失败", table_exists=exists)
    except Exception as e:
        logger.error("WIDE_DETAIL 重建失败: %s", e, exc_info=True)
        return RefreshResponse(success=False, message=f"WIDE_DETAIL 重建失败: {e}", table_exists=False)


@router.get("/api/admin/health")
async def health_check():
    """健康检查"""
    exists = wide_detail_table_exists()
    return {
        "status": "healthy",
        "wide_detail_exists": exists,
        "version": "1.0.0",
    }
