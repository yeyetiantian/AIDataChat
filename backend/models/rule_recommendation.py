"""规则配置推荐的领域模型。

这些模型是 Agent、API 和前端之间的稳定契约。LLM 只填写候选方案，
实体存在性和逻辑完整性由 ``RuleRecommendationValidator`` 负责校验。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EntityReference(BaseModel):
    """可追溯到业务元数据的实体引用。"""

    type: Literal["task", "existing_rule", "function", "signal", "alarm_stat"]
    id: str = ""
    label: str = ""
    detail: str = ""


class TaskReference(BaseModel):
    id: int | None = None
    name: str = ""


class AlarmSummary(BaseModel):
    """报警统计的口径和可用性必须一起返回。"""

    period_start: str | None = None
    period_end: str | None = None
    alarm_count: int = 0
    sample_count: int = 0
    source_status: Literal["available", "no_data", "unavailable"] = "unavailable"
    updated_at: str | None = None


class RecommendationEvidence(BaseModel):
    existing_rule_ids: list[int] = Field(default_factory=list)
    signal_names: list[str] = Field(default_factory=list)
    alarm_summary: AlarmSummary = Field(default_factory=AlarmSummary)


class FunctionCall(BaseModel):
    """规则表达式中的一个函数调用。"""

    function_id: int | None = None
    function_name: str = ""
    args: dict[str, object] = Field(default_factory=dict)


class LogicNode(BaseModel):
    """递归逻辑树。leaf 节点使用 function；组合节点使用 operator + children。"""

    operator: Literal["AND", "OR", "NOT", "LEAF"] = "LEAF"
    function: FunctionCall | None = None
    children: list["LogicNode"] = Field(default_factory=list)
    description: str = ""


class RecommendedSignal(BaseModel):
    name: str
    role: Literal["primary", "auxiliary", "filter", "output"] = "primary"
    required: bool = True
    rationale: str = ""


class RuleParameter(BaseModel):
    name: str
    value: object | None = None
    unit: str = ""
    rationale: str = ""


class ProposedRule(BaseModel):
    name: str = ""
    description: str = ""
    start_condition: LogicNode | None = None
    judge_condition: LogicNode | None = None
    end_condition: LogicNode | None = None
    signals: list[RecommendedSignal] = Field(default_factory=list)
    parameters: list[RuleParameter] = Field(default_factory=list)
    before_seconds: float | None = None
    after_seconds: float | None = None


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: str = ""
    severity: Literal["error", "warning"] = "error"


class RecommendationValidation(BaseModel):
    status: Literal["valid", "needs_confirmation", "invalid"] = "needs_confirmation"
    issues: list[ValidationIssue] = Field(default_factory=list)


class RuleConfigRecommendation(BaseModel):
    """一份可展示、可校验、可保存为草案的规则配置建议。"""

    recommendation_type: Literal[
        "new_rule", "adjust_existing", "reuse_existing", "insufficient_data"
    ] = "insufficient_data"
    business_goal: str = ""
    task: TaskReference = Field(default_factory=TaskReference)
    evidence: RecommendationEvidence = Field(default_factory=RecommendationEvidence)
    proposed_rule: ProposedRule = Field(default_factory=ProposedRule)
    validation: RecommendationValidation = Field(default_factory=RecommendationValidation)
    citations: list[EntityReference] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


LogicNode.model_rebuild()
