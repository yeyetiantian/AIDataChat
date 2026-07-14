from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class FilterItem(BaseModel):
    """筛选器 → SQL WHERE"""
    field: str = Field(..., description="字段名: task, vehicle, rule 等")
    op: str = Field("eq", description="操作符: in, eq, =, !=, >, >=, <, <=, between, like, contains, starts_with, ends_with, is_null, is_not_null")
    value: Any = Field(None, description="筛选值")
    select_ts: Optional[str] = Field(None, description="筛选时间戳")
    select_order: Optional[int] = Field(None, description="筛选顺序")
    filter_type: Optional[str] = Field("", description="筛选类型")


class AxisItem(BaseModel):
    """轴 → SQL GROUP BY"""
    field: str = Field(..., description="字段名")
    alias: Optional[str] = Field(None, description="别名")
    aggregation: Optional[str] = Field(None, description="时间粒度: year, quarter, month, week, day, hour")

class LegendItem(BaseModel):
    """图例 → SQL PIVOT ON"""
    field: str = Field(..., description="字段名")
    alias: Optional[str] = Field(None, description="别名")

class ShowAs(BaseModel):
    """值显示方式"""
    type: Literal[
        "normal",
        "column_percentage",
        "row_percentage",
        "total_percentage",
        "difference",
        "running_total",
        "rank_asc",
        "rank_desc",
    ] = Field("normal", description="显示方式")
    base_field: Optional[str] = Field(None, description="基准列（difference 模式使用）")
    running_field: Optional[str] = Field(None, description="排序字段（running_total 模式使用）")
    partition_field: Optional[str] = Field(None, description="分区字段（row_percentage 模式使用）")

class ValueItem(BaseModel):
    """值 → SQL 聚合"""
    field: Optional[str] = Field(None, description="字段名")
    aggregation: Optional[Literal["source","count", "sum", "avg", "min", "max"]] = Field(None, description="聚合函数")
    alias: Optional[str] = Field(None, description="别名")
    show_as: Optional[ShowAs] = Field(None, description="值显示方式")

class FilterOnAgg(BaseModel):
    """聚合后过滤 → SQL HAVING"""
    field: str = Field(..., description="字段名")
    op: str = Field(..., description="操作符")
    value: Any = Field(..., description="值")

class OrderBy(BaseModel):
    """排序"""
    field: str = Field(..., description="字段名")
    direction: Literal["asc", "desc"] = Field("desc", description="排序方向")

class PivotConfig(BaseModel):
    """完整表配置"""
    filters: list[FilterItem] = Field(default_factory=list, description="筛选器 → WHERE")
    axes: list[AxisItem] = Field(default_factory=list, description="轴 → GROUP BY")
    legend: list[LegendItem] = Field(default_factory=list, description="图例 → PIVOT ON")
    values: list[ValueItem] = Field(default_factory=list, description="值 → 聚合")
    # 扩展属性
    having: list[FilterOnAgg] = Field(default_factory=list, description="HAVING 子句（兼容字段）")
    order_by: list[OrderBy] = Field(default_factory=list, description="排序")
    chart_type: Optional[str] = Field(None, description="图表类型：bar/line/area/point/pie/radar")
    grand_total: bool = Field(False, description="是否显示总计")
    subtotals: bool = Field(False, description="是否显示小计")
    limit: int = Field(1000, description="无过滤时最大返回条数", ge=1, le=1000)

class PivotResponse(BaseModel):
    """表 API 响应"""
    data: list[dict[str, Any]] = Field(..., description="聚合结果数据")
    columns: list[str] = Field(..., description="列名列表")
    total: int = Field(0, description="总条数（分页用）")
    vega_spec: dict[str, Any] = Field(default_factory=dict, description="Vega-Lite 图表规格")
    config: PivotConfig = Field(..., description="回显配置")
    sql: Optional[str] = Field(None, description="生成的 SQL（调试用）")
    execution_time_ms: float = Field(0, description="执行耗时（毫秒）")

class RuleRecommendation(BaseModel):
    """规则函数推荐"""
    rule_name: str = Field(..., description="规则名称")
    rule_type: Optional[str] = Field(None, description="规则类型")
    description: str = Field("", description="规则功能说明")
    priority: Optional[str] = Field(None, description="优先级/重要程度")


class ChatRequest(BaseModel):
    """AI 对话请求"""
    message: str = Field(..., description="用户自然语言输入")
    session_id: Optional[str] = Field(None, description="会话 ID，首次请求不传则自动生成")

class ChatResponse(BaseModel):
    """AI 对话响应"""
    reply: str = Field(..., description="AI 回复文本")
    charts: list[dict[str, Any]] = Field(default_factory=list, description="图表列表（每个元素含 pivot_config/data/sql/chart_type）")
    suggestions: list[str] = Field(default_factory=list, description="AI 推荐的下一个问题")
    rules: list[dict[str, Any]] = Field(default_factory=list, description="规则函数推荐列表")
    session_id: str = Field("", description="会话 ID")
    trace_id: str = Field("", description="Agent 执行 trace ID")
    is_dashboard: bool = Field(False, description="是否为看板模式（多图表一起展示）")
    charts_count: int = Field(0, description="图表数量（看板模式下生效）")
    execution_time_ms: float = Field(0, description="执行耗时")
    ask_questions: list[dict[str, Any]] = Field(default_factory=list, description="交互式问卷（需用户进一步输入时返回）")
    pending_step: Optional[str] = Field(None, description="挂起步骤标识（如 awaiting_questions）")
    dashboard_draft_id: str = Field("", description="结构化看板草案 ID")
