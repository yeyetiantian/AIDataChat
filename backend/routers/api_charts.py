"""图表看板 API — CRUD

存储方式：本地 JSON 文件（charts.json）
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("api_charts")

router = APIRouter(prefix="/api/charts", tags=["charts"])

# 数据文件路径（相对于 backend/ 目录）
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_backend_dir, "data")
DATA_FILE = os.path.join(DATA_DIR, "charts.json")
_lock = threading.Lock()


def _ensure_data_dir():
    """确保 data/ 目录和 charts.json 文件存在"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def _read_all() -> list[dict[str, Any]]:
    """读取全部图表列表（按 updated_at 降序）"""
    _ensure_data_dir()
    try:
        with _lock:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, list):
            data = []
        # 按更新时间降序
        data.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return data
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _write_all(data: list[dict[str, Any]]):
    """写入全部图表列表"""
    _ensure_data_dir()
    with _lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# ============================================================
# Pydantic 模型
# ============================================================

class ChartCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="图表标题")
    description: str = Field("", max_length=500, description="描述")
    pivot_config: dict[str, Any] = Field(..., description="完整 PivotConfig JSON")
    chart_type: str = Field("bar", description="图表类型: bar, line, pie, area")
    data: list[dict[str, Any]] | None = Field(None, description="查询结果数据")


class ChartUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=500)
    pivot_config: dict[str, Any] | None = None
    chart_type: str | None = None
    data: list[dict[str, Any]] | None = None


class ChartResponse(BaseModel):
    id: int
    title: str
    description: str
    pivot_config: dict[str, Any]
    chart_type: str
    data: list[dict[str, Any]] | None = None
    created_at: str
    updated_at: str


# ============================================================
# API 路由
# ============================================================

@router.get("")
async def list_charts():
    """获取所有已保存的图表"""
    return _read_all()


@router.post("", response_model=ChartResponse)
async def save_chart(chart: ChartCreate):
    """保存当前图表配置"""
    all_charts = _read_all()
    now = datetime.now().isoformat()

    # 自增 ID
    max_id = max((c.get("id", 0) for c in all_charts), default=0)
    new_id = max_id + 1

    new_chart = {
        "id": new_id,
        "title": chart.title,
        "description": chart.description,
        "pivot_config": chart.pivot_config,
        "chart_type": chart.chart_type,
        "data": chart.data,
        "created_at": now,
        "updated_at": now,
    }

    all_charts.append(new_chart)
    _write_all(all_charts)

    logger.info("图表已保存: id=%s title=%s data_rows=%s", new_id, chart.title, len(chart.data) if chart.data else 0)
    return new_chart


@router.get("/{chart_id}", response_model=ChartResponse)
async def get_chart(chart_id: int):
    """获取单个图表配置"""
    all_charts = _read_all()
    for c in all_charts:
        if c["id"] == chart_id:
            return c
    raise HTTPException(status_code=404, detail="图表不存在")


@router.put("/{chart_id}", response_model=ChartResponse)
async def update_chart(chart_id: int, chart: ChartUpdate):
    """更新图表配置"""
    all_charts = _read_all()
    for c in all_charts:
        if c["id"] == chart_id:
            if chart.title is not None:
                c["title"] = chart.title
            if chart.description is not None:
                c["description"] = chart.description
            if chart.pivot_config is not None:
                c["pivot_config"] = chart.pivot_config
            if chart.chart_type is not None:
                c["chart_type"] = chart.chart_type
            if chart.data is not None:
                c["data"] = chart.data
            c["updated_at"] = datetime.now().isoformat()
            _write_all(all_charts)
            return c
    raise HTTPException(status_code=404, detail="图表不存在")


@router.delete("/{chart_id}")
async def delete_chart(chart_id: int):
    """删除图表"""
    all_charts = _read_all()
    before = len(all_charts)
    all_charts = [c for c in all_charts if c["id"] != chart_id]
    if len(all_charts) == before:
        raise HTTPException(status_code=404, detail="图表不存在")
    _write_all(all_charts)
    return {"success": True, "message": f"图表 {chart_id} 已删除"}
