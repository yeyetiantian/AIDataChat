"""结构化看板草案契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardChartSlot(BaseModel):
    index: int = Field(..., ge=1, le=6)
    description: str = ""
    preferred_chart_type: str | None = None


class DashboardRequestDraft(BaseModel):
    """问卷提交的原始选择；保留 ID，禁止仅靠中文文本回推。"""

    draft_id: str | None = None
    goal: str = "报警分析总览"
    task_id: int
    chart_count: int = Field(3, ge=1, le=6)
    rule_ids: list[int] = Field(default_factory=list)
    signal_names: list[str] = Field(default_factory=list)
    time_range: dict[str, str] | None = None
    chart_slots: list[DashboardChartSlot] = Field(default_factory=list)

