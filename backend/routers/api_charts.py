"""图表看板 API — CRUD（SQLite 持久化，支持多看板）"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.chat_db import list_charts, get_chart, create_chart, update_chart, delete_chart

logger = logging.getLogger("api_charts")
router = APIRouter(prefix="/api/charts", tags=["charts"])


class ChartCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=500)
    pivot_config: dict[str, Any] = Field(...)
    chart_type: str = Field("bar")
    data: list[dict[str, Any]] | None = Field(None)
    board_id: int = Field(..., description="所属看板 ID")
    user_id: int = Field(1, description="创建人")


class ChartUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=500)
    pivot_config: dict[str, Any] | None = None
    chart_type: str | None = None
    data: list[dict[str, Any]] | None = None


class ChartResponse(BaseModel):
    id: int
    board_id: int | None = None
    title: str
    description: str
    pivot_config: dict[str, Any]
    chart_type: str
    data: list[dict[str, Any]] | None = None
    created_at: str
    updated_at: str


@router.get("", response_model=list[ChartResponse])
async def get_charts(board_id: int = Query(..., description="看板 ID")):
    """获取指定看板下的所有图表"""
    return list_charts(board_id)


@router.post("", response_model=ChartResponse)
async def save_chart(chart: ChartCreate):
    """保存图表配置"""
    result = create_chart(
        user_id=chart.user_id,
        title=chart.title,
        pivot_config=chart.pivot_config,
        chart_type=chart.chart_type,
        description=chart.description,
        data=chart.data,
        board_id=chart.board_id,
    )
    logger.info("图表已保存: id=%s title=%s board_id=%s", result["id"], chart.title, chart.board_id)
    return result


@router.get("/{chart_id}", response_model=ChartResponse)
async def get_single_chart(chart_id: int):
    c = get_chart(chart_id)
    if not c:
        raise HTTPException(status_code=404, detail="图表不存在")
    return c


@router.put("/{chart_id}", response_model=ChartResponse)
async def update_single_chart(chart_id: int, chart: ChartUpdate):
    result = update_chart(
        chart_id=chart_id,
        title=chart.title,
        description=chart.description,
        pivot_config=chart.pivot_config,
        chart_type=chart.chart_type,
        data=chart.data,
    )
    if not result:
        raise HTTPException(status_code=404, detail="图表不存在")
    return result


@router.delete("/{chart_id}")
async def remove_chart(chart_id: int):
    ok = delete_chart(chart_id)
    if not ok:
        raise HTTPException(status_code=404, detail="图表不存在")
    return {"success": True}
