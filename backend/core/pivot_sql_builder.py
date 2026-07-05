"""表 SQL 生成器

基于 PivotConfig 生成 DuckDB SQL 的 9 步流水线。
数据来源支持两种模式：
  1. WIDE_DETAIL 明细宽表（默认）：8 固定字段 + 动态信号列，以 CTE 方式构建
  2. 原 6 表 LEFT JOIN（legacy 回退）：用于未使用 WIDE_DETAIL 字段的场景
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from core.db_connector import get_conn
from models import PivotConfig

logger = logging.getLogger("pivot_sql_builder")

# 源表 JOIN SQL
SOURCE_TABLES_JOIN = """FROM TL_RMU_PS_TASK_RULE_RESULT res
LEFT JOIN TM_RMU_PS_TASK_RULE r ON res.TASK_RULE_ID = r.TASK_RULE_ID
LEFT JOIN TM_RMU_PS_TASK t ON r.TASK_ID = t.TASK_ID
LEFT JOIN TM_RMU_PS_TASK_VEHICLE v ON res.VEHICLE_SID = v.VEHICLE_ID AND v.TASK_ID = t.TASK_ID
LEFT JOIN TM_RMU_PS_TASK_VEHICLETYPE vt ON v.TASK_VEHICLETYPE_ID = vt.TASK_VEHICLETYPE_ID
LEFT JOIN TL_RMU_PS_TASK_RULE_RESULT_SIGNAL sig ON res.TASK_RULE_RESULT_ID = sig.TASK_RULE_RESULT_ID"""

# 完整的 104 个字段显式 SELECT 列表（与 field_registry 命名 1:1 对齐）
# 顺序：任务表(33) → 规则表(23) → 结果表(24) → 车辆表(13) → 车型表(3) → 信号表(8)
EXPLICIT_SELECT_COLUMNS = """
    -- 任务表 t (33 字段，无前缀)
    t.TASK_ID,
    t.TASK_NAME,
    t.TASK_TYPE,
    t.TASK_PRIORITY,
    t.TASK_DB_MODE,
    t.TASK_START_TIME,
    t.TASK_END_TIME,
    t.TASK_EXECUTE_START_TIME,
    t.TASK_EXECUTE_END_TIME,
    t.ANALYSIS_STATE,
    t.RMUDATA_STATE,
    t.MERGE_STATE,
    t.APPROVE_STATE,
    t.APPROVE_REMARK,
    t.IS_DELETE,
    t.CREATE_BY,
    t.CREATE_TIME,
    t.UPDATE_BY,
    t.UPDATE_TIME,
    t.EXTRA1,
    t.EXTRA2,
    t.EXTRA3,
    t.VESCOM_ID,
    t.IS_PUBLIC,
    t.CREATE_BY_CODE,
    t.UPDATE_BY_CODE,
    t.REPORT_ID,
    t.IS_NOTICE,
    t.WARNING_TIMES,
    t.CYCLE,
    t.UNIT,
    t.WARNING_TIME,
    t.DATASOURCE,

    -- 规则表 r (23 字段，RULE_ 前缀)
    r.TASK_RULE_ID            AS RULE_TASK_RULE_ID,
    r.TASK_ID                 AS RULE_TASK_ID,
    r.RULE_NAME               AS RULE_NAME,
    r.RULE_DESCRIPTION        AS RULE_DESCRIPTION,
    r.RULE_MODE               AS RULE_MODE,
    r.START_EXPRESSION        AS START_EXPRESSION,
    r.START_EXPRESSION_CONVERT AS START_EXPRESSION_CONVERT,
    r.START_EXPRESSION_ID     AS START_EXPRESSION_ID,
    r.START_EXPRESSION_PARAM   AS START_EXPRESSION_PARAM,
    r.END_EXPRESSION          AS END_EXPRESSION,
    r.END_EXPRESSION_CONVERT  AS END_EXPRESSION_CONVERT,
    r.END_EXPRESSION_ID       AS END_EXPRESSION_ID,
    r.END_EXPRESSION_PARAM    AS END_EXPRESSION_PARAM,
    r.JUDGE_EXPRESSION        AS JUDGE_EXPRESSION,
    r.JUDGE_EXPRESSION_CONVERT AS JUDGE_EXPRESSION_CONVERT,
    r.JUDGE_EXPRESSION_ID     AS JUDGE_EXPRESSION_ID,
    r.JUDGE_EXPRESSION_PARAM  AS JUDGE_EXPRESSION_PARAM,
    r.RULE_TYPE               AS RULE_TYPE,
    r.RULE_END_TIME           AS RULE_END_TIME,
    r.RBF_BEFORE_TIME         AS RBF_BEFORE_TIME,
    r.RBF_AFTER_TIME          AS RBF_AFTER_TIME,
    r.RULE_SIGNALS            AS RULE_SIGNALS,
    r.OTHER_SIGNALS           AS OTHER_SIGNALS,

    -- 结果表 res (24 字段，无前缀，VALUE→RESULT_VALUE)
    res.TASK_RULE_RESULT_ID,
    res.TASK_RULE_ID,
    res.VEHICLE_SID,
    res.VIN,
    res.RMU_CODE,
    res.FILE_NAME,
    res.TIME,
    res.VALUE                 AS RESULT_VALUE,
    res.RMU_FILE_STATE,
    res.RBF_FILE_ID,
    res.RBF_STATE,
    res.RBF_REMARK,
    res.MF4_FILE_ID,
    res.MF4_STATE,
    res.MF4_REMARK,
    res.VSB_FILE_ID,
    res.VSB_STATE,
    res.VSB_REMARK,
    res.ASC_FILE_ID,
    res.ASC_STATE,
    res.ASC_REMARK,
    res.EXIT_TIME,
    res.TRIGGER_TIME,
    res.MASTER_ID,

    -- 车辆表 v (13 字段，TVEHICLE_ 前缀 + 特殊名)
    v.TASK_VEHICLE_ID         AS TVEHICLE_TASK_VEHICLE_ID,
    v.TASK_VEHICLETYPE_ID     AS TVEHICLE_TASK_VEHICLETYPE_ID,
    v.VEHICLE_ID              AS TVEHICLE_VEHICLE_ID,
    v.TASK_ID                 AS TVEHICLE_TASK_ID,
    v.VIN                     AS TVEHICLE_VIN,
    v.VIN_PATAC_ID            AS VIN_PATAC_ID,
    v.RMU_CODE                AS TVEHICLE_RMU_CODE,
    v.STATE                   AS VEHICLE_STATE,
    v.EXTRA1                  AS TVEHICLE_EXTRA1,
    v.EXTRA2                  AS TVEHICLE_EXTRA2,
    v.EXTRA3                  AS TVEHICLE_EXTRA3,
    v.IS_DEL                  AS IS_DEL,
    v.UPDATE_TIME             AS TVEHICLE_UPDATE_TIME,

    -- 车型表 vt (3 字段)
    vt.TASK_VEHICLETYPE_ID    AS VTYPE_TASK_VEHICLETYPE_ID,
    vt.TASK_ID               AS VTYPE_TASK_ID,
    vt.VEHICLETYPE_NAME       AS VEHICLETYPE_NAME,

    -- 信号表 sig (8 字段，前缀 SIGNAL_ + 特殊名)
    sig.RULE_RESULT_SIGNAL_ID AS RULE_RESULT_SIGNAL_ID,
    sig.TASK_RULE_RESULT_ID   AS SIGNAL_TASK_RULE_RESULT_ID,
    sig.TYPE                  AS SIGNAL_TYPE,
    sig.SIGNAL_NAME           AS SIGNAL_NAME,
    sig.VALUE                 AS SIGNAL_VALUE,
    sig.EXTRA_1               AS SIGNAL_EXTRA_1,
    sig.EXTRA_2               AS SIGNAL_EXTRA_2,
    sig.EXTRA_3               AS SIGNAL_EXTRA_3
""".strip()

# DuckDB 时间粒度函数映射
GROUP_FUNCTIONS: dict[str, str] = {
    "year": "date_trunc('year', {})",
    "quarter": "date_trunc('quarter', {})",
    "month": "date_trunc('month', {})",
    "week": "date_trunc('week', {})",
    "day": "date_trunc('day', {})",
    "hour": "date_trunc('hour', {})",
}

OP_MAP: dict[str, str] = {
    "=": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<=",
    "between": "BETWEEN", "in": "IN", "like": "LIKE",
    "contains": "LIKE", "starts_with": "LIKE", "ends_with": "LIKE",
    "is_null": "IS NULL", "is_not_null": "IS NOT NULL",
}


def _to_dict(obj: Any) -> dict[str, Any]:
    """将 Pydantic model 或 dict 统一转为 dict"""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if hasattr(obj, "dict"):
        return obj.dict(exclude_none=True)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return dict(obj)


def _sql_quote(value: str) -> str:
    """安全引用 SQL 字符串值（转义单引号，检测表达式不引）"""
    # 检测 SQL 表达式：函数调用、关键字、运算符号
    if re.search(r"\w+\s*\(", value) or re.search(r"\b(INTERVAL|SELECT|CASE|NOW|DATE_TRUNC|EXTRACT)\b", value, re.IGNORECASE):
        return value
    return f"'{value.replace(chr(39), chr(39)+chr(39))}'"


def _build_where_clause(filters: list[Any]) -> str:
    """构建 WHERE 子句"""
    if not filters:
        return ""
    clauses: list[str] = []
    for f in filters:
        d = _to_dict(f)
        field = d.get("field", "")
        op = d.get("op", "=")
        value = d.get("value")

        if op in ("is_null", "is_not_null"):
            clauses.append(f'"{field}" {OP_MAP[op]}')
            continue
        if op == "between":
            vals = value if isinstance(value, (list, tuple)) else []
            if len(vals) >= 2:
                clauses.append(f'"{field}" BETWEEN {_sql_quote(str(vals[0]))} AND {_sql_quote(str(vals[1]))}')
            continue
        if op == "in":
            vals = value if isinstance(value, (list, tuple)) else [value]
            formatted = ", ".join(_sql_quote(str(v)) for v in vals)
            clauses.append(f'"{field}" IN ({formatted})')
            continue
        if op in ("contains", "like"):
            clauses.append(f'"{field}" LIKE \'%{value}%\'')
            continue
        if op == "starts_with":
            clauses.append(f'"{field}" LIKE \'{value}%\'')
            continue
        if op == "ends_with":
            clauses.append(f'"{field}" LIKE \'%{value}\'')
            continue
        if isinstance(value, str):
            clauses.append(f'"{field}" {OP_MAP[op]} {_sql_quote(value)}')
        else:
            clauses.append(f'"{field}" {OP_MAP[op]} {value}')
    return " AND ".join(clauses) if clauses else ""


def _axis_expr(d: dict[str, Any], include_alias: bool = True) -> str:
    """轴字段表达式"""
    field = d["field"]
    group = d.get("group")
    alias = d.get("alias")
    expr = GROUP_FUNCTIONS[group].format(f'"{field}"') if group and group in GROUP_FUNCTIONS else f'"{field}"'
    if include_alias:
        alias_name = alias or field
        return f'{expr} AS "{alias_name}"'
    return expr


def _group_field(d: dict[str, Any]) -> str:
    """GROUP BY 表达式"""
    field = d["field"]
    group = d.get("group")
    if group and group in GROUP_FUNCTIONS:
        return GROUP_FUNCTIONS[group].format(f'"{field}"')
    return f'"{field}"'


def _value_expr(d: dict[str, Any], for_pivot: bool = False, is_wide_signal: bool = False) -> str:
    """值表达式。

    Args:
        is_wide_signal: True 表示该字段是「明细宽表」的动态信号列（VARCHAR 存储），
                         聚合时先 TRY_CAST 成 DOUBLE，避免 AVG/SUM 字符串报错。
    """
    field = d.get("field")
    aggregation = d.get("aggregation")
    alias = d.get("alias") or d.get("id", "val")
    expr = d.get("expr")

    # 非数值固定字段集合（sum/avg/min/max 对它们无意义 → 兜底为 count）
    _NON_NUMERIC_FIXED = {
        "person", "vehicle_type", "vehicle", "task",
        "rule_name", "rule_type", "expression",
        "condition_met_time", "alarm_time",
        "alarm_value", "freeze_frame",
    }

    # 检测是否需要兜底：非数值字段 + 非 count 聚合
    _NEEDS_FALLBACK = (
        not is_wide_signal
        and not expr
        and field in _NON_NUMERIC_FIXED
        and aggregation
        and aggregation not in ("count", "count_distinct", "distinct")
    )
    if _NEEDS_FALLBACK:
        aggregation = "count"

    # 动态信号列：先 TRY_CAST 到 DOUBLE
    def _col_ref() -> str:
        if is_wide_signal and not expr:
            return f'TRY_CAST("{field}" AS DOUBLE)'
        return f'"{field}"'

    if expr:
        agg_expr = expr
    elif aggregation in ("count_distinct", "distinct"):
        agg_expr = f'count(DISTINCT {_col_ref()})'
    elif aggregation == "count":
        agg_expr = f'count("{field}")'
    elif aggregation:
        agg_expr = f'{aggregation}({_col_ref()})'
    else:
        agg_expr = f'count("{field}")'

    # 使用 field 作为 SQL 列名，alias 仅做显示用
    col_name = field or alias
    return agg_expr if for_pivot else f'{agg_expr} AS "{col_name}"'


class PivotSQLBuilder:
    """表 SQL 生成器"""

    def __init__(self, config: PivotConfig):
        cfg = _to_dict(config)
        self.filters: list[dict] = cfg.get("filters", [])
        self.axes: list[dict] = cfg.get("axes", [])
        self.legend: list[dict] = cfg.get("legend", [])
        self.values: list[dict] = cfg.get("values", [])
        self.row_filters: list[dict] = cfg.get("row_filters", [])
        self.col_filters: list[dict] = cfg.get("col_filters", [])
        self.having: list[dict] = cfg.get("having", [])
        self.top_n: dict | None = cfg.get("top_n")
        self.grand_total: bool = cfg.get("grand_total", False)
        self.subtotals: bool = cfg.get("subtotals", False)
        self.limit_val: int = cfg.get("limit", 10000)
        self.calculated_fields: list[dict] = cfg.get("calculated_fields", [])
        self.calculated_items: list[dict] = cfg.get("calculated_items", [])
        self.order_by: list[dict] = cfg.get("order_by", [])
        self.pagination: dict | None = cfg.get("pagination")
        self._dynamic_columns: list[str] = []
        # PIVOT 模式下 value id → 实际列名的映射（构建 PIVOT 时填充）
        self._pivot_value_col_map: dict[str, str] = {}

        # =============== 宽表模式 (明细宽表) 判定 ===============
        from core.field_registry import (
            WIDE_DETAIL_FIXED_KEYS,
        )
        # 已知非信号列 = 宽表固定 12 字段
        self._fixed_wide_keys = set(WIDE_DETAIL_FIXED_KEYS)
        self._all_fields: set[str] = self._collect_fields()
        # 明细宽表模式判定：所有引用列中，只要有一个是固定宽表列，就用宽表模式
        self.use_wide_detail: bool = bool(self._all_fields & self._fixed_wide_keys)
        # 宽表中需要查询的信号名集合：不在 12 个固定列里的，都视为信号列
        #（宽表已预构建全部信号列，按名直接查询即可）
        self.wide_signal_names: set[str] = {
            f for f in self._all_fields
            if f not in self._fixed_wide_keys
        }
        if self.use_wide_detail:
            logger.info(
                "命中明细宽表模式：固定列 %s 个, 信号列 %s 个 (%s)",
                len(self._all_fields & self._fixed_wide_keys),
                len(self.wide_signal_names),
                ", ".join(sorted(self.wide_signal_names)[:10])
                + ("..." if len(self.wide_signal_names) > 10 else ""),
            )

    def _collect_fields(self) -> set[str]:
        s: set[str] = set()

        def add(d: dict | None):
            if not isinstance(d, dict):
                return
            for k in ("field", "base_field", "partition_field", "running_field", "by"):
                v = d.get(k)
                if isinstance(v, str) and v:
                    s.add(v)

        for f in self.filters: add(f)
        for a in self.axes: add(a)
        for l in self.legend: add(l)
        for v in self.values: add(v)
        for f in self.row_filters: add(f)
        for f in self.col_filters: add(f)
        for f in (self.having or []): add(f)
        for f in self.calculated_fields:
            if isinstance(f, dict) and f.get("name"):
                s.add(str(f["name"]))
        for f in self.calculated_items:
            if isinstance(f, dict):
                add(f)
                if f.get("name"): s.add(str(f["name"]))
        for o in self.order_by:
            # order_by 的 field 可能是 value id（如 val_1），不是实际列名，跳过
            v = o.get("field")
            if isinstance(v, str) and v and not v.startswith("val_"):
                s.add(v)
        if isinstance(self.top_n, dict): add(self.top_n)
        return s

    def build(self) -> tuple[str, list]:
        """生成完整 SQL"""
        cte_parts = []
        base_sql = self._build_base_cte()
        cte_parts.append(f"base_data AS ({base_sql})")

        if self.legend:
            grouped_sql = self._build_pivot()
        else:
            grouped_sql = self._build_group_by()
        cte_parts.append(f"grouped_data AS ({grouped_sql})")
        current = "grouped_data"

        needs_dynamic = self.legend and any(
            v.get("show_as") and v["show_as"].get("type", "normal") != "normal"
            for v in self.values
        )
        if needs_dynamic:
            self._capture_dynamic_columns()

        has_show_as = any(
            v.get("show_as") and v["show_as"].get("type", "normal") != "normal"
            for v in self.values
        )
        if has_show_as:
            show_sql = self._build_show_as(current)
            cte_parts.append(f"show_as_data AS ({show_sql})")
            current = "show_as_data"

        if self.row_filters or self.col_filters:
            having_sql = self._build_having(current)
            cte_parts.append(f"filtered_data AS ({having_sql})")
            current = "filtered_data"

        if self.top_n and self.top_n.get("enabled"):
            topn_sql = self._build_top_n(current)
            cte_parts.append(f"top_n_data AS ({topn_sql})")
            current = "top_n_data"

        if self.grand_total or self.subtotals:
            totals_sql = self._build_totals(current)
            cte_parts.append(f"totals_data AS ({totals_sql})")
            current = "totals_data"

        order_clause = self._build_order_by()
        limit_clause, offset_clause = self._build_pagination()

        final_sql = f"SELECT * FROM {current}{order_clause}{limit_clause}{offset_clause}"
        full_sql = "WITH " + ",\n".join(cte_parts) + "\n" + final_sql
        return full_sql, []

    def _build_base_cte(self) -> str:
        """Step 1: Base CTE
        - 明细宽表模式 (use_wide_detail=True): 构建 _wide_base + _wide_sig + _wide_pivoted 三层 CTE 得到 wide 字段
        - 源表模式 (默认): 用显式列 SELECT + 6 表 LEFT JOIN，别名与 field_registry 完全对齐
        """
        if self.use_wide_detail:
            return self._build_wide_base_cte()
        return self._build_legacy_base_cte()

    def _build_legacy_base_cte(self) -> str:
        """原 6 表 JOIN 模式（保留给老接口/源表字段使用）"""
        where = _build_where_clause(self.filters)
        has_time = any(f.get("field") in ("TRIGGER_TIME", "TIME", "EXIT_TIME", "TASK_START_TIME") for f in self.filters)
        has_task = any(f.get("field") == "TASK_ID" for f in self.filters)

        sql = f"SELECT\n{EXPLICIT_SELECT_COLUMNS}"

        # 添加计算字段（calculated_fields）
        for cf in self.calculated_fields:
            name = cf.get("name", "")
            formula = cf.get("formula", "")
            if name and formula:
                sql += f",\n    {formula} AS \"{name}\""

        # 添加计算项（calculated_items）— 用 CASE WHEN 合并分类
        for ci in self.calculated_items:
            ci_name = ci.get("name", "")
            ci_field = ci.get("field", "")
            ci_formula = ci.get("formula", "")
            if ci_name and ci_field and ci_formula:
                values = [v.strip() for v in ci_formula.replace("+", ",").split(",") if v.strip()]
                in_clause = ", ".join(f"'{v}'" for v in values)
                sql += (
                    f",\n    CASE WHEN \"{ci_field}\" IN ({in_clause}) THEN '{ci_name}' ELSE \"{ci_field}\"::VARCHAR END AS \"{ci_name}\""
                )

        sql += f"\n{SOURCE_TABLES_JOIN}"

        if where:
            sql += f"\nWHERE {where}"
        if not has_time and not has_task:
            sql += f"\nLIMIT {self.limit_val}"
        return sql

    # ----------------------------------------------------------
    # 明细宽表模式 (WIDE_DETAIL)：直接查询预构建的 WIDE_DETAIL 表
    # 列:  person, vehicle_type, vehicle, task, rule_name, rule_type, expression,
    #       condition_met_time, alarm_time, duration_sec, alarm_value, freeze_frame
    #       + 若干信号名 (UDat_13 / PrplsnSysAtv / IBSBatSOC / ...)
    # ----------------------------------------------------------
    def _build_wide_base_cte(self) -> str:
        """直接 SELECT * FROM WIDE_DETAIL（从 ATTACH 的宽表库），不再构建复杂 CTE。

        列名已在宽表中存在（固定 12 字段 + 全部动态信号列），
        只需挑选查询中用到的信号列即可。
        """
        sig_names = sorted(self.wide_signal_names)

        # ---------- SELECT 列：固定 12 字段 + 查询中用到的信号列 ----------
        select_cols = [
            "person", "vehicle_type", "vehicle", "task",
            "rule_name", "rule_type", "expression",
            "condition_met_time", "alarm_time", "duration_sec",
            "alarm_value", "freeze_frame",
        ]

        def esc(s: str) -> str:
            return s.replace("'", "''")

        for n in sig_names:
            select_cols.append(f'"{esc(n)}"')

        cols_sql = ",\n    ".join(select_cols)

        # ---------- 构造查询 ----------
        # 先用 EXISTS 判断 WIDE_DETAIL 表是否可访问
        sql = f"SELECT\n    {cols_sql}\nFROM WIDE_DETAIL"

        # 在外层加上 filters
        where = _build_where_clause(self.filters)
        if where:
            sql += f"\nWHERE {where}"

        return self._apply_wide_calculated_fields(sql)

    def _apply_wide_calculated_fields(self, sql: str, from_alias: str = "") -> str:
        """在宽表 SELECT 末尾追加 calculated_fields / calculated_items 派生列。
        这里实现为在外层再包一层 SELECT，避免 PIVOT 内部别名冲突。"""
        if not self.calculated_fields and not self.calculated_items:
            return sql
        select_cols = ["person","vehicle_type","vehicle","task","rule_name","rule_type","expression","condition_met_time","alarm_time","duration_sec","alarm_value","freeze_frame"]
        select_cols.extend(sorted(self.wide_signal_names))
        all_cols = [f'"{c}"' for c in select_cols]
        append: list[str] = []
        for cf in self.calculated_fields:
            name = cf.get("name", "")
            formula = cf.get("formula", "")
            if name and formula:
                append.append(f"{formula} AS \"{name}\"")
                all_cols.append(f'"{name}"')
        for ci in self.calculated_items:
            ci_name = ci.get("name", "")
            ci_field = ci.get("field", "")
            ci_formula = ci.get("formula", "")
            if ci_name and ci_field and ci_formula:
                values = [v.strip() for v in ci_formula.replace("+", ",").split(",") if v.strip()]
                in_clause = ", ".join(f"'{v}'" for v in values)
                append.append(
                    f"CASE WHEN \"{ci_field}\" IN ({in_clause}) THEN '{ci_name}' ELSE \"{ci_field}\"::VARCHAR END AS \"{ci_name}\""
                )
                all_cols.append(f'"{ci_name}"')
        if not append:
            return sql
        cols = ",\n    ".join(all_cols[:8 + len(self.wide_signal_names)] + append)
        # 子查询起别名为 src
        return (
            f"WITH _src AS (\n{sql}\n)\n"
            f"SELECT {cols}\nFROM _src src"
        )

    def _build_group_by(self) -> str:
        """Step 2（无 Pivot）"""
        if not self.axes:
            parts = ["'source' AS _source"]
            parts.extend(
                _value_expr(v, is_wide_signal=self._is_wide_signal(v.get("field")))
                for v in self.values
            )
            return f"SELECT {', '.join(parts)} FROM base_data"
        select_exprs = [_axis_expr(a) for a in self.axes]
        select_exprs.extend(
            _value_expr(v, is_wide_signal=self._is_wide_signal(v.get("field")))
            for v in self.values
        )
        group = ", ".join(_group_field(a) for a in self.axes)
        return f"SELECT {', '.join(select_exprs)}\nFROM base_data\nGROUP BY {group}"

    def _build_pivot(self) -> str:
        """Step 2（有 Pivot）。

        兼容 DuckDB v1.x：用「条件聚合 CASE WHEN」手动展开 PIVOT（Tableau 经典方式）。
        因为 DuckDB 1.5 只支持 `PIVOT (... FOR col IN (literal1, literal2,...))` 这种写死字面量的旧语法，
        不支持 `PIVOT ON (col) USING ... GROUP BY` 新语法。
        """
        if not self.legend:
            # 无 legend 走 group by 路径
            return self._build_group_by()

        legend_values = self._legend_value_tuples()
        axis_select = [_axis_expr(a) for a in self.axes]
        axis_group = ", ".join(_group_field(a) for a in self.axes) if self.axes else "()"
        pivot_cols: list[str] = []

        for lv in legend_values:
            # lv: dict[legend_field → value]
            where_parts: list[str] = []
            col_name_parts: list[str] = []
            for l in self.legend:
                v = lv[l["field"]]
                if v is None:
                    where_parts.append(f'"{l["field"]}" IS NULL')
                    col_name_parts.append("NULL")
                else:
                    sv = str(v).replace("'", "''")
                    where_parts.append(f'"{l["field"]}" = \'{sv}\'')
                    col_name_parts.append(str(v))
            cond = " AND ".join(where_parts)
            col_label = "_".join(col_name_parts)
            for vdef in self.values:
                alias = vdef.get("alias") or vdef.get("id", "val")
                # 列名: 如 "报警_AVG_UDat_13"
                pivot_col_name = f"{col_label}_{alias}" if col_label else alias
                val_sql_agg = _value_expr(
                    vdef, for_pivot=True,
                    is_wide_signal=self._is_wide_signal(vdef.get("field"))
                )
                # 将 "agg(col)" → "agg(CASE WHEN cond THEN col END)" 重写
                # 最简单：用 agg(CASE WHEN cond THEN col_ref ELSE NULL END)
                field = vdef.get("field")
                expr = vdef.get("expr")
                agg = vdef.get("aggregation") or "count"
                if expr:
                    col_ref = expr  # 已直接写表达式
                else:
                    col_ref = (
                        f'TRY_CAST("{field}" AS DOUBLE)'
                        if self._is_wide_signal(field)
                        else f'"{field}"'
                    )

                if agg in ("count_distinct", "distinct"):
                    agg_inner = f'COUNT(DISTINCT CASE WHEN {cond} THEN {col_ref} END)'
                elif agg == "count":
                    agg_inner = f'COUNT(CASE WHEN {cond} THEN {col_ref} END)'
                else:
                    agg_inner = f'{agg}(CASE WHEN {cond} THEN {col_ref} END)'
                pivot_cols.append(f'{agg_inner} AS "{pivot_col_name}"')
            # 记录第一个图例组合的列名，供 ORDER BY 使用
            vid = vdef.get("id")
            if vid and vid not in self._pivot_value_col_map:
                self._pivot_value_col_map[vid] = pivot_col_name

        if axis_select:
            select_sql = ", ".join(axis_select + pivot_cols)
            return f"SELECT {select_sql}\nFROM base_data\nGROUP BY {axis_group}"
        select_sql = ", ".join(pivot_cols)
        return f"SELECT {select_sql}\nFROM base_data"

    def _legend_value_tuples(self) -> list[dict[str, Any]]:
        """查询 legend 字段在 base_data 里的唯一值组合（用于 CASE WHEN 展开列名）。

        为性能，最多取前 50 个组合。
        """
        try:
            legend_fields = [l["field"] for l in self.legend]
            select = ", ".join(f'"{f}"' for f in legend_fields)
            group = ", ".join(f'"{f}"' for f in legend_fields)
            # base_data (wide CTE) 自身已经包含嵌套 WITH，DuckDB 可直接引用
            sql = f"WITH base_data AS ({self._build_base_cte()}) SELECT {select} FROM base_data GROUP BY {group} ORDER BY {group} LIMIT 50"
            conn = get_conn()
            rows = conn.execute(sql).fetchall()
            result: list[dict[str, Any]] = []
            for r in rows:
                result.append({legend_fields[i]: r[i] for i in range(len(legend_fields))})
            return result
        except Exception as e:
            logger.warning("查询 legend 唯一值失败，用空 PIVOT: %s", e)
            return []

    def _is_wide_signal(self, field: str | None) -> bool:
        return bool(self.use_wide_detail and field and field in self.wide_signal_names)

    def _capture_dynamic_columns(self) -> None:
        """Step 3: 动态列名（CASE WHEN PIVOT 模式下直接跑 grouped_data CTE 的 LIMIT 0 获取列名）"""
        try:
            grouped_sql = self._build_pivot()
            conn = get_conn()
            full = f"WITH base_data AS ({self._build_base_cte()})\nSELECT * FROM ({grouped_sql}) LIMIT 0"
            conn.execute(full)
            all_cols = [desc[0] for desc in conn.description]
            axis_fields = {a.get("alias") or a["field"] for a in self.axes}
            self._dynamic_columns = [c for c in all_cols if c not in axis_fields]
        except Exception as e:
            logger.warning("动态列名捕获失败: %s", e)
            self._dynamic_columns = []

    def _build_show_as(self, src: str) -> str:
        """Step 4: Show As"""
        selects = [f"{src}.*"]
        for v in self.values:
            sa = v.get("show_as")
            if not sa or sa.get("type", "normal") == "normal":
                continue
            # 获取实际列名：PIVOT 模式用 _pivot_value_col_map，GROUP BY 模式用 field
            if self.legend:
                col = self._pivot_value_col_map.get(v.get("id"), v.get("id"))
            else:
                col = v.get("field") or v.get("alias") or v.get("id")
            st = sa.get("type")
            if st == "column_percentage":
                selects.append(f'"{col}" / NULLIF(SUM("{col}") OVER (), 0) AS "{col}_百分比"')
            elif st == "row_percentage":
                pf = sa.get("partition_field")
                if pf:
                    selects.append(f'"{col}" / NULLIF(SUM("{col}") OVER (PARTITION BY "{pf}"), 0) AS "{col}_行百分比"')
            elif st == "total_percentage":
                selects.append(f'"{col}" / NULLIF(SUM("{col}") OVER (), 0) AS "{col}_占比"')
            elif st == "difference":
                base = sa.get("base_field")
                if base:
                    selects.append(f'"{col}" - "{base}" AS "{col}_差值"')
            elif st == "running_total":
                rf = sa.get("running_field") or (self.axes[0]["field"] if self.axes else "TRIGGER_TIME")
                selects.append(f'SUM("{col}") OVER (ORDER BY "{rf}") AS "{col}_累计"')
            elif st in ("rank_asc", "rank_desc"):
                od = "ASC" if st == "rank_asc" else "DESC"
                selects.append(f'RANK() OVER (ORDER BY "{col}" {od}) AS "{col}_排名"')
        return f"SELECT {', '.join(selects)}\nFROM {src}"

    def _build_having(self, src: str) -> str:
        """Step 5: HAVING"""
        all_f = self.row_filters + self.col_filters
        if not all_f:
            return f"SELECT * FROM {src}"
        clauses: list[str] = []
        for f in all_f:
            field, op, value = f["field"], f["op"], f.get("value")
            if op in ("is_null", "is_not_null"):
                clauses.append(f'"{field}" IS {"NOT " if op == "is_not_null" else ""}NULL')
            elif op == "between":
                vals = value if isinstance(value, (list, tuple)) else []
                if len(vals) >= 2:
                    clauses.append(f'"{field}" BETWEEN {vals[0]} AND {vals[1]}')
            elif op in ("contains", "like"):
                clauses.append(f'"{field}" LIKE \'%{value}%\'')
            elif op == "in":
                vals = value if isinstance(value, (list, tuple)) else [value]
                formatted = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in vals)
                clauses.append(f'"{field}" IN ({formatted})')
            else:
                val_str = f"'{value}'" if isinstance(value, str) else str(value)
                clauses.append(f'"{field}" {OP_MAP.get(op, "=")} {val_str}')
        return f"SELECT * FROM {src}\nHAVING {' AND '.join(clauses)}"

    def _build_totals(self, src: str) -> str:
        """Step 6: 总计 + 分层小计 (ROLLUP)

        例: axes = [A, B, C]
            - 原始行:  GROUP BY A, B, C  (来自上一步 CTE)
            - 小计1:   GROUP BY A, B      (C 维度汇总)
            - 小计2:   GROUP BY A         (B, C 维度汇总)
            - 总计:    GROUP BY ()        (全部汇总)
        """
        if not self.axes:
            return f"SELECT * FROM {src}"

        axis_fields = [a.get("alias") or a["field"] for a in self.axes]
        val_cols = [v["field"] for v in self.values]

        selects: list[str] = [f"SELECT * FROM {src}"]

        def build_aggregate(keep_axis_count: int, label_suffix: str = "") -> str:
            """生成 N-1 维度小计的 SELECT。keep_axis_count 保留前几个轴字段。"""
            col_parts: list[str] = []
            for i, ax in enumerate(axis_fields):
                if i < keep_axis_count:
                    col_parts.append(f'"{ax}"')
                else:
                    col_parts.append(f"NULL AS \"{ax}\"")
            for vc in val_cols:
                # 尝试使用 sum/min/max 做兼容合并；计数/求和最常用
                col_parts.append(f'SUM("{vc}") AS "{vc}"')
            group_cols = ", ".join(f'"{ax}"' for ax in axis_fields[:keep_axis_count])
            where = " WHERE " + " AND ".join(
                f'"{ax}" IS NOT NULL' for ax in axis_fields[:keep_axis_count]
            ) if keep_axis_count > 0 else ""
            group_by = f"\nGROUP BY {group_cols}" if group_cols else ""
            return f"SELECT {', '.join(col_parts)}\nFROM {src}{where}{group_by}"

        # 分层小计（从 完整维度-1 到 1）
        if self.subtotals and len(self.axes) >= 2:
            for keep in range(len(self.axes) - 1, 0, -1):
                selects.append(build_aggregate(keep))

        # 总计
        if self.grand_total:
            selects.append(build_aggregate(0))

        return "\nUNION ALL\n".join(selects)

    def _build_top_n(self, src: str) -> str:
        """Step 7: TOP N"""
        tn = self.top_n
        if not tn or not tn.get("enabled"):
            return f"SELECT * FROM {src}"
        by = tn["by"]
        count = tn.get("count", 10)
        direction = "DESC" if tn.get("type", "top") == "top" else "ASC"

        # 使用值的别名作为排序列名
        by_column = by
        if by in self._pivot_value_col_map:
            by_column = self._pivot_value_col_map[by]
        else:
            for v in self.values:
                if v.get("id") == by:
                    by_column = v.get("field") or v.get("alias") or v["id"]
                    break

        return f"SELECT * FROM {src}\nQUALIFY ROW_NUMBER() OVER (ORDER BY \"{by_column}\" {direction}) <= {count}"

    def _build_order_by(self) -> str:
        """Step 8: ORDER BY（自动将 value id 解析为实际列名）"""
        if not self.order_by:
            return ""
        clauses: list[str] = []
        for ob in self.order_by:
            field = ob["field"]
            # PIVOT 模式：优先使用 _pivot_value_col_map
            if field in self._pivot_value_col_map:
                field = self._pivot_value_col_map[field]
            else:
                # 非 PIVOT 模式：如果 field 是 value 的 id（如 "val_1"），解析为实际 SQL 列名
                for v in self.values:
                    if v.get("id") == field:
                        field = v.get("field") or v.get("alias") or field
                        break
            clauses.append(f'"{field}" {ob.get("direction", "desc")}')
        return f"\nORDER BY {', '.join(clauses)}"

    def _build_pagination(self) -> tuple[str, str]:
        """Step 9: 分页"""
        p = self.pagination
        if not p:
            return "", ""
        page = p.get("page", 1)
        ps = p.get("pageSize", 100)
        offset = (page - 1) * ps
        return f"\nLIMIT {ps}", f"\nOFFSET {offset}"


def execute_pivot(config: PivotConfig) -> dict[str, Any]:
    """执行表查询"""
    start = time.time()
    builder = PivotSQLBuilder(config)
    sql, _ = builder.build()
    logger.debug("生成 SQL: %s", sql)

    conn = get_conn()
    try:
        result = conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        data = [dict(zip(columns, row)) for row in rows]
        elapsed = (time.time() - start) * 1000

        # 生成 Vega-Lite spec（后端生成基础结构，前端会补充数据）
        vega_spec = build_vega_spec(config)

        return {
            "data": data,
            "columns": columns,
            "total": len(rows),
            "vega_spec": vega_spec,
            "config": config,
            "sql": sql,
            "execution_time_ms": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error("查询失败: %s\nSQL: %s", e, sql, exc_info=True)
        raise


def build_vega_spec(config: PivotConfig) -> dict[str, Any]:
    """根据 PivotConfig 生成 Vega-Lite 规格"""
    cfg = _to_dict(config)
    axes = cfg.get("axes", [])
    values = cfg.get("values", [])
    legend = cfg.get("legend", [])
    chart_type = cfg.get("chart_type")  # 前端选中的图表类型

    has_legend = bool(legend)
    has_multi_values = len(values) > 1

    # ── 确定图表类型 ──
    has_time = bool(axes and axes[0].get("group"))
    if chart_type and chart_type != "auto":
        # 前端指定
        pass
    else:
        # 自动推断
        chart_type = "line" if has_time else "bar"

    # ── 构建编码 ──
    encoding: dict[str, Any] = {}

    # X 轴
    if axes:
        a0 = axes[0]
        ax_name = a0.get("alias") or a0["field"]
        is_time = a0.get("group") is not None

        if has_time and legend:
            # 时间 + 图例 → 多系列折线图
            chart_type = "line"
            encoding["x"] = {"field": ax_name, "type": "temporal", "title": ax_name}
        elif is_time:
            chart_type = "line"
            encoding["x"] = {"field": ax_name, "type": "temporal", "title": ax_name}
        else:
            encoding["x"] = {"field": ax_name, "type": "nominal", "title": ax_name}
            if not legend and not has_multi_values:
                encoding["x"]["sort"] = "-y"
    else:
        encoding["x"] = {"field": "_source", "type": "nominal", "title": "总计"}

    # Y 轴 + 多值处理
    if has_multi_values:
        # 多个值 → 用 fold 变换实现多系列（列名为 field，与 SQL 输出对齐）
        val_names = [v.get("field") or v.get("alias") or v.get("id") for v in values]
        encoding["y"] = {"field": "value", "type": "quantitative", "title": "数值"}
        encoding["color"] = {
            "field": "key", "type": "nominal", "title": "指标",
        }
        # 使用 transform 的 fold
        spec: dict[str, Any] = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": "数据分析",
            "data": {"values": []},
            "transform": [{"fold": val_names, "as": ["key", "value"]}],
            "mark": {"type": chart_type, "tooltip": True, "point": chart_type == "line"},
            "encoding": encoding,
        }
    else:
        # 单值
        first_val = values[0] if values else {}
        val_name = first_val.get("field") or first_val.get("alias") or first_val.get("id", "count")
        if legend:
            # 有图例 → 堆叠/分组条形图
            legend_field = legend[0]
            legend_name = legend_field.get("alias") or legend_field["field"]
            encoding["y"] = {"field": val_name, "type": "quantitative", "title": first_val.get("alias") or val_name}
            encoding["color"] = {"field": legend_name, "type": "nominal", "title": legend_name}
        else:
            encoding["y"] = {"field": val_name, "type": "quantitative", "title": first_val.get("alias") or val_name}

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": "数据分析",
            "data": {"values": []},
            "mark": {"type": chart_type, "tooltip": True, "point": chart_type == "line"},
            "encoding": encoding,
        }

    return spec
