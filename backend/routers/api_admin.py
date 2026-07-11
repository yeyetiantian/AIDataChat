"""数据库 + 字段 / Schema / 管理接口

管理接口：
- POST /api/admin/refresh_wide_detail — 手动触发 重建
- GET /api/admin/health — 健康检查
- GET /api/fields — 字段列表（供前端拖拽）
- POST /api/admin/reset-fields — 重置字段为硬编码数据
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from core.field_registry import get_fields_grouped, get_schema_markdown

logger = logging.getLogger("api_admin")

router = APIRouter(tags=["admin"])


class RefreshResponse(BaseModel):
    success: bool
    message: str
    table_exists: bool = False


@router.get("/api/fields")
async def get_fields():
    return get_fields_grouped()
