"""图表类型字段规格注册表 — 定义每类图表对 PivotConfig 的字段需求约束。

所有消费者（chart_agent prompt、api_recommend 规则引擎）
统一从这里读取，保持唯一事实来源。
"""

from __future__ import annotations

from typing import TypedDict


class ChartFieldSpec(TypedDict, total=False):
    """单类图表的字段规格"""
    label: str                               # 中文名
    description: str                         # 给 LLM 看的说明
    axes_min: int                            # 最少轴数
    axes_max: int | None                     # 最多轴数（None 表示不限制）
    axes_time_required: bool                 # 轴是否必须为时间字段
    values_min: int                          # 最少聚合值数
    values_max: int | None                   # 最多聚合值数（None 表示不限制）
    values_allowed_aggregation: list[str]    # 允许的聚合方式
    legend_allowed: bool                     # 是否允许图例
    recommendation_priority: int             # 通用场景推荐优先级（越小越优先）


CHART_TYPE_SPECS: dict[str, ChartFieldSpec] = {
    "bar": {
        "label": "柱状图",
        "description": "比较各类别间的数值大小，轴至少 1 个非时间维度，支持分组柱状图（图例）",
        "axes_min": 1,
        "axes_max": 2,
        "axes_time_required": False,
        "values_min": 1,
        "values_max": None,
        "values_allowed_aggregation": ["source", "count", "sum", "avg", "min", "max"],
        "legend_allowed": True,
        "recommendation_priority": 1,
    },
    "line": {
        "label": "折线图",
        "description": "展示数据随时间或顺序变化的趋势，轴需包含时间字段，支持多系列对比（图例）",
        "axes_min": 1,
        "axes_max": 2,
        "axes_time_required": True,
        "values_min": 1,
        "values_max": 3,
        "values_allowed_aggregation": ["source", "count", "sum", "avg", "min", "max"],
        "legend_allowed": True,
        "recommendation_priority": 2,
    },
    "area": {
        "label": "面积图",
        "description": "强调时间序列上的量级变化和累积效果，轴为时间字段",
        "axes_min": 1,
        "axes_max": 1,
        "axes_time_required": True,
        "values_min": 1,
        "values_max": 2,
        "values_allowed_aggregation": ["source", "count", "sum", "avg"],
        "legend_allowed": True,
        "recommendation_priority": 4,
    },
    "point": {
        "label": "散点图",
        "description": "探索双数值维度的相关性和分布，至少 2 个值或 2 个轴",
        "axes_min": 1,
        "axes_max": 3,
        "axes_time_required": False,
        "values_min": 1,
        "values_max": 3,
        "values_allowed_aggregation": ["source", "count", "sum", "avg", "min", "max"],
        "legend_allowed": False,
        "recommendation_priority": 4,
    },
    "pie": {
        "label": "饼图",
        "description": "展示各部分占整体的比例，轴恰好 1 个且非时间字段，值 1 个，不支持图例",
        "axes_min": 1,
        "axes_max": 1,
        "axes_time_required": False,
        "values_min": 1,
        "values_max": 1,
        "values_allowed_aggregation": ["source", "count", "sum"],
        "legend_allowed": False,
        "recommendation_priority": 3,
    },
    "radar": {
        "label": "雷达图",
        "description": "多指标综合对比，轴 1 个，值至少 3 个，不支持图例",
        "axes_min": 1,
        "axes_max": 1,
        "axes_time_required": False,
        "values_min": 3,
        "values_max": None,
        "values_allowed_aggregation": ["source", "count", "sum", "avg", "min", "max"],
        "legend_allowed": False,
        "recommendation_priority": 5,
    },
}


def get_chart_type_specs_text() -> str:
    """将规格注册表渲染为 LLM prompt 可用的 Markdown 文本。"""
    lines = ["# Chart Type Specifications\n"]
    for chart_type, spec in CHART_TYPE_SPECS.items():
        parts = [f"- `{chart_type}`: {spec['description']}"]
        constraints = []
        constraints.append(f"轴: {spec['axes_min']}~{spec['axes_max'] or '不限'}个")
        constraints.append(f"值: {spec['values_min']}~{spec['values_max'] or '不限'}个")
        constraints.append(f"聚合: {'/'.join(spec['values_allowed_aggregation'])}")
        constraints.append(f"图例: {'✓' if spec['legend_allowed'] else '✗'}")
        if spec.get("axes_time_required"):
            constraints.append("（轴需含时间字段）")
        parts.append("  " + " ｜ ".join(constraints))
        lines.append("\n".join(parts))
    return "\n".join(lines)
