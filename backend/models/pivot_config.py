"""Pivot 配置 Pydantic 模型（严格四属性 JSON）

对应需求文档第 5 节的核心数据模型。
"""

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
    aggregation: Optional[str] = Field(None, description="时间粒度: year, quarter, month, week, day, hour（替代 group）")
    group: Optional[str] = Field(None, description="（已废弃，请用 aggregation）时间粒度: year, quarter, month, week, day, hour")
    sort: Optional[Literal["asc", "desc"]] = Field("asc", description="排序方向")


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
    id: str = Field(..., description="唯一标识，如 val_1")
    field: Optional[str] = Field(None, description="字段名（与 expr 互斥）")
    aggregation: Optional[Literal["count", "sum", "avg", "min", "max", "count_distinct", "distinct"]] = Field(None, description="聚合函数")
    alias: Optional[str] = Field(None, description="别名")
    expr: Optional[str] = Field(None, description="直接表达式（与 field+aggregation 互斥）")
    show_as: Optional[ShowAs] = Field(None, description="值显示方式")

    @model_validator(mode="after")
    def validate_field_or_expr(self) -> "ValueItem":
        if not self.expr and not self.field:
            raise ValueError("field 或 expr 必须提供一个")
        if self.field and not self.aggregation:
            raise ValueError("field 存在时必须指定 aggregation")
        return self


class FilterOnAgg(BaseModel):
    """聚合后过滤 → SQL HAVING"""
    field: str = Field(..., description="字段名（可引用别名）")
    op: str = Field(..., description="操作符")
    value: Any = Field(..., description="值")


class TopN(BaseModel):
    """TOP N 筛选"""
    enabled: bool = Field(False, description="是否启用")
    count: int = Field(10, description="取前 N 条")
    by: str = Field(..., description="排序依据的 value id")
    type: Literal["top", "bottom"] = Field("top", description="top 或 bottom")


class CalculatedField(BaseModel):
    """计算字段"""
    name: str = Field(..., description="字段名")
    formula: str = Field(..., description="公式表达式")


class CalculatedItem(BaseModel):
    """计算项（对某个字段的值做分类合并）"""
    name: str = Field(..., description="项名称")
    field: str = Field(..., description="源字段")
    formula: str = Field(..., description="公式，如 'SUV + MPV + 轿车'")


class OrderBy(BaseModel):
    """排序"""
    field: str = Field(..., description="排序字段")
    direction: Literal["asc", "desc"] = Field("desc", description="排序方向")


class Pagination(BaseModel):
    """分页"""
    page: int = Field(1, description="页码", ge=1)
    pageSize: int = Field(100, description="每页条数", ge=1, le=10000)


class PivotConfig(BaseModel):
    """完整表配置（严格四属性）"""
    filters: list[FilterItem] = Field(default_factory=list, description="筛选器 → WHERE")
    axes: list[AxisItem] = Field(default_factory=list, description="轴 → GROUP BY")
    legend: list[LegendItem] = Field(default_factory=list, description="图例 → PIVOT ON")
    values: list[ValueItem] = Field(default_factory=list, description="值 → 聚合")

    # 扩展属性
    row_filters: list[FilterOnAgg] = Field(default_factory=list, description="行过滤 → HAVING（维度字段）")
    col_filters: list[FilterOnAgg] = Field(default_factory=list, description="列过滤 → HAVING（聚合值）")
    having: list[FilterOnAgg] = Field(default_factory=list, description="HAVING 子句（兼容字段）")
    top_n: Optional[TopN] = Field(None, description="TOP N")
    calculated_fields: list[CalculatedField] = Field(default_factory=list, description="计算字段")
    calculated_items: list[CalculatedItem] = Field(default_factory=list, description="计算项")
    order_by: list[OrderBy] = Field(default_factory=list, description="排序")
    pagination: Optional[Pagination] = Field(None, description="分页")
    chart_type: Optional[str] = Field(None, description="图表类型：bar/line/area/point/pie/radar")
    grand_total: bool = Field(False, description="是否显示总计")
    subtotals: bool = Field(False, description="是否显示小计")
    limit: int = Field(10000, description="无过滤时最大返回条数", ge=1, le=100000)


class PivotResponse(BaseModel):
    """表 API 响应"""
    data: list[dict[str, Any]] = Field(..., description="聚合结果数据")
    columns: list[str] = Field(..., description="列名列表")
    total: int = Field(0, description="总条数（分页用）")
    vega_spec: dict[str, Any] = Field(default_factory=dict, description="Vega-Lite 图表规格")
    config: PivotConfig = Field(..., description="回显配置")
    sql: Optional[str] = Field(None, description="生成的 SQL（调试用）")
    execution_time_ms: float = Field(0, description="执行耗时（毫秒）")


class ChatRequest(BaseModel):
    """AI 对话请求"""
    message: str = Field(..., description="用户自然语言输入")
    history: list[dict[str, str]] = Field(default_factory=list, description="对话历史")


class ChatResponse(BaseModel):
    """AI 对话响应"""
    reply: str = Field(..., description="AI 回复文本")
    charts: list[dict[str, Any]] = Field(default_factory=list, description="图表列表（每个元素含 pivot_config/data/sql/chart_type）")
    suggestions: list[str] = Field(default_factory=list, description="AI 推荐的下一个问题")
    execution_time_ms: float = Field(0, description="执行耗时")
    execution_time_ms: float = Field(0, description="执行耗时")


# =============================================================================
# 明细宽表：8 固定字段 + 信号名动态 PIVOT 展开
# =============================================================================

FIXED_COLUMN_DEFS: list[dict[str, Any]] = [
    {"key": "person",           "label": "人员",                     "data_type": "VARCHAR",  "width": 180},
    {"key": "vehicle_type",     "label": "车型",                     "data_type": "VARCHAR",  "width": 200},
    {"key": "vehicle",          "label": "车辆",                     "data_type": "VARCHAR",  "width": 220},
    {"key": "task",             "label": "任务",                     "data_type": "VARCHAR",  "width": 280},
    {"key": "rule_name",        "label": "规则名称",                 "data_type": "VARCHAR",  "width": 280},
    {"key": "rule_type",        "label": "规则类型",                 "data_type": "VARCHAR",  "width": 100},
    {"key": "expression",       "label": "表达式",                   "data_type": "VARCHAR",  "width": 260},
    {"key": "condition_met_time","label": "前置条件满足时间",         "data_type": "TIMESTAMP","width": 200},
    {"key": "alarm_time",       "label": "报警时间/前置条件不满足时间","data_type": "TIMESTAMP","width": 200},
    {"key": "duration_sec",     "label": "持续秒",                   "data_type": "DOUBLE",   "width": 110},
    {"key": "alarm_value",      "label": "报警/统计数据",            "data_type": "VARCHAR",  "width": 180},
    {"key": "freeze_frame",     "label": "冻结帧",                   "data_type": "VARCHAR",  "width": 260},
]

RULE_TYPE_MAP = {0: "统计", 1: "报警", 2: "事件"}


class DetailQuery(BaseModel):
    """明细宽表查询请求"""
    # 固定字段筛选（都为 AND 关系；列表项 = IN / 字符串用 LIKE）
    person: Optional[list[str]] = Field(None, description="筛选人员姓名列表（IN）")
    vehicle_type: Optional[list[str]] = Field(None, description="筛选车型名称列表（IN）")
    vehicle: Optional[list[str]] = Field(None, description="筛选车辆 VIN 列表（IN）")
    task: Optional[list[str]] = Field(None, description="筛选任务名称列表（可模糊：字符串含 % 即走 LIKE）")
    rule_name: Optional[list[str]] = Field(None, description="筛选规则名称列表（可模糊）")
    rule_type: Optional[list[int]] = Field(None, description="筛选规则类型值 0=统计 / 1=报警 / 2=事件")
    expression: Optional[list[str]] = Field(None, description="筛选表达式（可模糊 LIKE）")

    # 时间区间
    condition_met_time_from: Optional[str] = Field(None, description="前置条件满足时间起（ISO 时间字符串）")
    condition_met_time_to:   Optional[str] = Field(None, description="前置条件满足时间止（ISO 时间字符串）")
    alarm_time_from: Optional[str] = Field(None, description="报警时间起（ISO 时间字符串）")
    alarm_time_to:   Optional[str] = Field(None, description="报警时间止（ISO 时间字符串）")
    duration_from:   Optional[float] = Field(None, description="持续时间起（秒）")
    duration_to:     Optional[float] = Field(None, description="持续时间止（秒）")

    # 文本筛选
    alarm_value:  Optional[list[str]] = Field(None, description="筛选报警/统计数据（可模糊 LIKE）")
    freeze_frame: Optional[list[str]] = Field(None, description="筛选冻结帧文件名（可模糊 LIKE）")

    # 信号列：显式指定信号名，或按频率自动 TOP-N
    signal_names:    Optional[list[str]] = Field(None, description="指定要展开的信号名列表；不填则按 frequency 取 TOP-N")
    top_n_signals:   int = Field(60, ge=1, le=500, description="未指定 signal_names 时，按关联频率自动取前 N 个信号")
    signal_value_max_len: int = Field(64, ge=1, le=2000, description="每个信号值截取长度（避免超长字符串拖慢）")

    # 排序
    order_by:  str = Field("alarm_time", description="排序列：默认报警时间；支持所有固定列 key 或任意信号名")
    order_dir: Literal["asc", "desc"] = Field("desc", description="排序方向")

    # 分页
    page:      int = Field(1, ge=1, description="页号，从 1 起")
    page_size: int = Field(50, ge=1, le=2000, description="每页大小")

    include_sql: bool = Field(False, description="是否返回生成的 SQL")


class DetailResponse(BaseModel):
    """明细宽表查询响应"""
    fixed_cols:     list[dict[str, Any]] = Field(..., description="固定列元数据")
    dynamic_cols:   list[dict[str, Any]] = Field(default_factory=list, description="动态展开的信号列元数据")
    columns:        list[str]            = Field(..., description="所有列的 key 顺序（固定列在前 + 动态信号列在后）")
    data:           list[dict[str, Any]] = Field(..., description="行数据")
    total:          int                  = Field(0, description="总行数（符合筛选条件的总条数）")
    page:           int                  = Field(1, description="当前页号")
    page_size:      int                  = Field(50, description="每页大小")
    signal_names:   list[str]            = Field(default_factory=list, description="实际展开的信号名列表")
    sql:            Optional[str]        = Field(None, description="生成的 SQL（include_sql=true）")
    execution_time_ms: float             = Field(0, description="执行耗时 ms")
