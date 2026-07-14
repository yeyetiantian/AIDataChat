"""面向业务目标的看板方案模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardChartPlan(BaseModel):
    index: int = Field(..., ge=1, le=6)
    role: str
    title_hint: str
    analysis_question: str
    preferred_chart_type: str
    slot_description: str = ""


class DashboardRecommendation(BaseModel):
    goal: str
    template_name: str
    task_id: int
    shared_constraints: list[str] = Field(default_factory=list)
    charts: list[DashboardChartPlan] = Field(default_factory=list)

