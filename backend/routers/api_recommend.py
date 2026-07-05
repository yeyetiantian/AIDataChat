"""POST /api/recommend-chart — 根据透视表配置推荐图表类型

基于 PivotConfig（axes、legend、values 等属性），
使用规则引擎分析字段特征，返回多个推荐的图表类型及评分。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models import PivotConfig

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
# 推荐规则
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


# ----- 各图表类型推荐规则 -----

def _recommend_pie(config: PivotConfig) -> ChartRec | None:
    """饼图：1 axis + 1 value + no legend，且不是时间字段"""
    if len(config.axes or []) != 1:
        return None
    if config.legend:
        return None
    if len(config.values or []) != 1:
        return None
    if _has_time_axis(config):
        return None
    return {
        "type": "pie",
        "score": 95,
        "reason": "单一维度 + 单一聚合值，适合饼图展示占比",
    }


def _recommend_line(config: PivotConfig) -> ChartRec | None:
    """折线图：轴字段是时间类型"""
    if not _has_time_axis(config):
        return None
    if len(config.axes or []) > 2:
        return None
    score = 90
    reasons = ["时间字段在轴中"]
    if len(config.axes or []) == 1 and not config.legend:
        reasons.append("单维度趋势")
        score = 95
    elif config.legend:
        reasons.append("多系列时间趋势")
    if len(config.values or []) > 1:
        reasons.append("多指标对比")
    return {
        "type": "line",
        "score": score,
        "reason": "，".join(reasons) + "，适合折线图展示趋势",
    }


def _recommend_area(config: PivotConfig) -> ChartRec | None:
    """面积图：时间轴 + 强调总量变化"""
    if not _has_time_axis(config):
        return None
    if len(config.axes or []) > 1:
        return None
    reasons = ["时间字段"]
    score = 75
    if config.legend:
        reasons.append("多系列")
        score = 70
    if _is_aggregation_count(config):
        reasons.append("计数聚合")
        score = 80
    return {
        "type": "area",
        "score": score,
        "reason": "，".join(reasons) + "，适合面积图强调量级变化",
    }


def _recommend_bar(config: PivotConfig) -> ChartRec | None:
    """柱状图：1-2 axis，适合类别对比"""
    if len(config.axes or []) == 0:
        return None
    if _all_axes_are_time(config):
        return None  # 时间优先推荐 line
    score = 85
    reasons = ["类别对比"]
    if config.legend:
        reasons.append("分组对比")
        score = 90
    if len(config.axes or []) == 2:
        reasons.append("双维度")
        score = 80
    if len(config.values or []) > 2:
        reasons.append("多指标")
    return {
        "type": "bar",
        "score": score,
        "reason": "，".join(reasons) + "，适合柱状图",
    }


def _recommend_point(config: PivotConfig) -> ChartRec | None:
    """散点图：2 values or 2 axes，探索相关性"""
    has_two_values = len(config.values or []) >= 2
    has_two_axes = len(config.axes or []) >= 2
    if not has_two_values and not has_two_axes:
        return None
    return {
        "type": "point",
        "score": 70 if has_two_values else 60,
        "reason": "多维度/多数值对比，适合散点图探索分布",
    }


def _recommend_radar(config: PivotConfig) -> ChartRec | None:
    """雷达图：1 axis + 3+ values，综合对比"""
    if len(config.axes or []) != 1:
        return None
    if len(config.values or []) < 3:
        return None
    return {
        "type": "radar",
        "score": 70,
        "reason": "多指标综合对比，适合雷达图",
    }


# ============================================================
# 推荐引擎入口
# ============================================================

def recommend_chart_types(config: PivotConfig) -> list[ChartRec]:
    """对 PivotConfig 执行规则推荐，返回按评分降序的图表类型列表"""
    recommenders = [
        _recommend_pie,
        _recommend_line,
        _recommend_area,
        _recommend_bar,
        _recommend_point,
        _recommend_radar,
    ]

    results: list[ChartRec] = []
    for rec_fn in recommenders:
        try:
            rec = rec_fn(config)
            if rec is not None:
                results.append(rec)
        except Exception as e:
            logger.warning("推荐函数 %s 异常: %s", rec_fn.__name__, e)

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
