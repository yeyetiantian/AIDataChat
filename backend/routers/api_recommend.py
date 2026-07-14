"""POST /api/recommend-chart — 根据透视表配置推荐图表类型

基于 PivotConfig（axes、legend、values 等属性），
使用 services.chart_type_specs 中的规格注册表进行推荐。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models import PivotConfig
from services.chart_type_specs import CHART_TYPE_SPECS, ChartFieldSpec

logger = logging.getLogger("api_recommend")

router = APIRouter(prefix="/api", tags=["recommend"])

# 时间相关字段名
TIME_FIELDS = frozenset({
    "alarm_time", "condition_met_time", "created_at", "updated_at",
    "timestamp", "date", "time", "year", "month", "day",
})


# ============================================================
# 请求/响应模型
# ============================================================

class RecommendRequest(BaseModel):
    """推荐图表请求"""
    config: PivotConfig = Field(..., description="报表配置")


class RecommendItem(BaseModel):
    """单个推荐项"""
    type: str = Field(..., description="图表类型：bar/line/area/point/pie/radar")
    score: int = Field(..., ge=0, le=100, description="推荐分数")
    reason: str = Field(..., description="推荐理由")


class RecommendResponse(BaseModel):
    """推荐图表响应"""
    recommendations: list[RecommendItem] = Field(..., description="推荐列表（按评分降序）")
    top: str = Field(..., description="最佳推荐图表类型")


# ============================================================
# 通用工具函数
# ============================================================

ChartRec = dict[str, Any]  # {"type": str, "score": int, "reason": str}


def _is_time_field(field: str) -> bool:
    """判断字段是否时间类型"""
    return field.lower() in TIME_FIELDS or any(
        kw in field.lower() for kw in ["time", "date", "timestamp"]
    )


def _has_time_axis(config: PivotConfig) -> bool:
    return any(_is_time_field(a.field) for a in (config.axes or []))


def _all_axes_are_time(config: PivotConfig) -> bool:
    axes = config.axes or []
    return len(axes) > 0 and all(_is_time_field(a.field) for a in axes)


def _is_aggregation_count(config: PivotConfig) -> bool:
    """是否全部或主要为 count 聚合"""
    values = config.values or []
    if not values:
        return True
    return all((v.aggregation or "count") == "count" for v in values)


# ============================================================
# 基于注册表的统一推荐逻辑
# ============================================================

def _recommend_by_spec(config: PivotConfig, chart_type: str, spec: ChartFieldSpec) -> ChartRec | None:
    """基于 CHART_TYPE_SPECS 注册表统一推荐。

    先检查基本约束（轴/值数量、图例、时间字段要求），
    再按图表类型追加特定评分和理由。
    """
    axes_count = len(config.axes or [])
    values_count = len(config.values or [])

    # --- 基本约束检查（源自 spec）---
    if axes_count < spec["axes_min"]:
        return None
    if spec.get("axes_max") is not None and axes_count > spec["axes_max"]:
        return None
    if values_count < spec["values_min"]:
        return None
    if spec.get("values_max") is not None and values_count > spec["values_max"]:
        return None
    if not spec.get("legend_allowed", True) and config.legend:
        return None
    if spec.get("axes_time_required") and not _has_time_axis(config):
        return None

    # --- 各图表类型的特异性排除 ---
    if chart_type == "bar" and _all_axes_are_time(config):
        return None

    # --- 评分和理由 ---
    if chart_type == "pie":
        score = 95
        reason = "单一维度 + 单一聚合值，适合饼图展示占比"

    elif chart_type == "line":
        reasons = ["时间字段在轴中"]
        score = 90
        if len(config.axes or []) == 1 and not config.legend:
            reasons.append("单维度趋势")
            score = 95
        elif config.legend:
            reasons.append("多系列时间趋势")
        if values_count > 1:
            reasons.append("多指标对比")
        reason = "，".join(reasons) + "，适合折线图展示趋势"

    elif chart_type == "area":
        reasons = ["时间字段"]
        score = 75
        if config.legend:
            reasons.append("多系列")
            score = 70
        if _is_aggregation_count(config):
            reasons.append("计数聚合")
            score = 80
        reason = "，".join(reasons) + "，适合面积图强调量级变化"

    elif chart_type == "bar":
        reasons = ["类别对比"]
        score = 85
        if config.legend:
            reasons.append("分组对比")
            score = 90
        if axes_count == 2:
            reasons.append("双维度")
            score = 80
        if values_count > 2:
            reasons.append("多指标")
        reason = "，".join(reasons) + "，适合柱状图"

    elif chart_type == "point":
        has_two_values = values_count >= 2
        has_two_axes = axes_count >= 2
        if not has_two_values and not has_two_axes:
            return None
        score = 70 if has_two_values else 60
        reason = "多维度/多数值对比，适合散点图探索分布"

    elif chart_type == "radar":
        score = 70
        reason = "多指标综合对比，适合雷达图"

    else:
        return None

    return {"type": chart_type, "score": score, "reason": reason}


# ============================================================
# 推荐引擎入口
# ============================================================

def recommend_chart_types(config: PivotConfig) -> list[ChartRec]:
    """对 PivotConfig 执行规则推荐，返回按评分降序的图表类型列表"""
    results: list[ChartRec] = []
    for chart_type, spec in CHART_TYPE_SPECS.items():
        try:
            rec = _recommend_by_spec(config, chart_type, spec)
            if rec is not None:
                results.append(rec)
        except Exception as e:
            logger.warning("推荐 %s 异常: %s", chart_type, e)

    results.sort(key=lambda r: r["score"], reverse=True)

    if not results:
        results.append({
            "type": "bar",
            "score": 50,
            "reason": "默认推荐：柱状图",
        })

    return results


# ============================================================
# API 端点
# ============================================================

@router.post("/recommend-chart", response_model=RecommendResponse)
async def recommend_chart(request: RecommendRequest):
    """根据表配置推荐最佳图表类型"""
    try:
        recs = recommend_chart_types(request.config)
        return RecommendResponse(
            recommendations=[RecommendItem(**r) for r in recs],
            top=recs[0]["type"],
        )
    except Exception as e:
        logger.error("图表推荐失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
