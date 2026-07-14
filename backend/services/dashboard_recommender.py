"""确定性看板方案模板。

模板给出每张图的业务职责，LLM 只负责在字段范围内完成 PivotConfig，
避免多张图重复或口径漂移。
"""

from __future__ import annotations

from models import DashboardRecommendation, DashboardRequestDraft
from models.dashboard_recommendation import DashboardChartPlan


_ALARM_OVERVIEW = [
    ("趋势", "报警趋势", "报警量随时间如何变化？", "line"),
    ("分布", "规则报警分布", "哪些规则贡献最多报警？", "bar"),
    ("排行", "车辆/车型报警排行", "哪些对象需要优先关注？", "bar"),
    ("时段", "报警时段分布", "报警集中发生在哪些时段？", "bar"),
    ("信号", "关联信号分析", "哪些信号最常关联报警？", "bar"),
    ("明细", "报警明细", "需要追溯哪些报警记录？", "point"),
]

_RULE_DIAGNOSIS = [
    ("趋势", "规则报警趋势", "规则报警是否有异常波动？", "line"),
    ("信号", "高报警关联信号", "哪些输入信号需要优先核查？", "bar"),
    ("对比", "规则对比", "当前规则之间的报警贡献如何？", "bar"),
    ("质量", "数据质量检查", "是否存在缺失或异常采样？", "bar"),
    ("排行", "高风险车辆排行", "哪些车辆需要优先排查？", "bar"),
    ("明细", "规则报警明细", "哪些记录支撑当前判断？", "point"),
]


def build_dashboard_recommendation(draft: DashboardRequestDraft) -> DashboardRecommendation:
    goal = draft.goal or "报警分析总览"
    template_name, template = (
        ("任务规则诊断", _RULE_DIAGNOSIS)
        if any(token in goal for token in ("规则", "诊断", "信号"))
        else ("报警总览", _ALARM_OVERVIEW)
    )
    slot_map = {slot.index: slot for slot in draft.chart_slots}
    charts: list[DashboardChartPlan] = []
    for index, (role, title, question, chart_type) in enumerate(template[:draft.chart_count], start=1):
        slot = slot_map.get(index)
        charts.append(DashboardChartPlan(
            index=index,
            role=role,
            title_hint=title,
            analysis_question=question,
            preferred_chart_type=(slot.preferred_chart_type if slot and slot.preferred_chart_type else chart_type),
            slot_description=slot.description if slot else "",
        ))
    constraints = [f"所有图表仅分析 TASK_ID={draft.task_id}", "报警口径在各图中保持一致"]
    if draft.rule_ids:
        constraints.append(f"优先覆盖已选规则：{draft.rule_ids}")
    if draft.signal_names:
        constraints.append(f"优先覆盖已选信号：{draft.signal_names}")
    if draft.time_range:
        constraints.append(f"共享时间范围：{draft.time_range}")
    return DashboardRecommendation(
        goal=goal, template_name=template_name, task_id=draft.task_id,
        shared_constraints=constraints, charts=charts,
    )


def dashboard_plan_prompt(draft: DashboardRequestDraft) -> str:
    plan = build_dashboard_recommendation(draft)
    lines = [f"## 推荐看板方案（{plan.template_name}）", f"目标：{plan.goal}", "共享约束："]
    lines.extend(f"- {constraint}" for constraint in plan.shared_constraints)
    lines.append("图表职责（按以下顺序生成，不可重复）：")
    for chart in plan.charts:
        lines.append(
            f"- 图表{chart.index} [{chart.role}]：{chart.title_hint}；问题：{chart.analysis_question}；"
            f"图形：{chart.preferred_chart_type}；用户补充：{chart.slot_description or '无'}"
        )
    return "\n".join(lines)
