"""大宽表字段注册表

字段信息从 WIDE_DETAIL 实际列名生成，缓存到本地 JSON 文件。
用于：
1. 前端字段列表展示
2. LangGraph Agent 的 Schema 注入
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from typing import Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("field_registry")

LOCK = threading.Lock()

if getattr(sys, "frozen", False):
    # PyInstaller 打包模式：data/ 在 sys._MEIPASS 下
    _backend_dir = sys._MEIPASS
else:
    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS_JSON = os.path.join(_backend_dir, "data", "wide_fields.json")


class FieldDef(BaseModel):
    """字段定义"""
    name: str = Field(..., description="字段名（大宽表中的列名）")
    alias_cn: str = Field(..., description="中文别名")
    data_type: str = Field(..., description="数据类型")
    source_table: str = Field(..., description="源表名")
    description: str = Field("", description="业务说明")
    category: Literal["id", "dimension", "measure", "time", "status", "file", "ext"] = Field(
        "dimension", description="字段分类"
    )
    example_values: Optional[str] = Field(None, description="示例值")
    in_wide_table: bool = Field(True, description="是否在大宽表中可用")


# ============================================================
# 明细宽表固定字段定义（硬编码）
# ============================================================

WIDE_DETAIL_TABLE = "WIDE_DETAIL"
WIDE_DETAIL_TABLE_CN = "明细宽表"

WIDE_DETAIL_FIXED_FIELDS: list[FieldDef] = [
    FieldDef(name="person",           alias_cn="人员",                     data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="vehicle_type",     alias_cn="车型",                     data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="vehicle",          alias_cn="车辆(VIN)",               data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="task",             alias_cn="任务",                     data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="rule_name",        alias_cn="规则名称",                 data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="rule_type",        alias_cn="规则类型",                 data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="expression",       alias_cn="表达式",                   data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="condition_met_time", alias_cn="前置条件满足时间",        data_type="TIMESTAMP", source_table=WIDE_DETAIL_TABLE, category="time"),
    FieldDef(name="alarm_time",       alias_cn="报警时间/前置条件不满足时间", data_type="TIMESTAMP", source_table=WIDE_DETAIL_TABLE, category="time"),
    FieldDef(name="duration_sec",     alias_cn="持续时间(秒)",             data_type="DOUBLE",    source_table=WIDE_DETAIL_TABLE, category="measure"),
    FieldDef(name="alarm_value",      alias_cn="报警/统计数据",            data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="measure"),
    FieldDef(name="freeze_frame",     alias_cn="冻结帧",                   data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
]
WIDE_DETAIL_FIXED_KEYS: set[str] = {f.name for f in WIDE_DETAIL_FIXED_FIELDS}


# ============================================================
# JSON 文件读写
# ============================================================

def _ensure_data_dir():
    os.makedirs(os.path.dirname(FIELDS_JSON), exist_ok=True)


def _save_fields_json(fields: list[dict]):
    """将字段列表写入 JSON 缓存"""
    _ensure_data_dir()
    with LOCK:
        with open(FIELDS_JSON, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False, indent=2)


def _load_fields_json() -> list[dict] | None:
    """从 JSON 缓存读取字段列表"""
    try:
        with LOCK:
            with open(FIELDS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ============================================================
# 从宽表实时同步信号列 → JSON 缓存
# ============================================================

def sync_fields_from_wide() -> list[dict]:
    """从 WIDE_DETAIL 表读取实际列名，生成完整字段列表并存入 JSON"""
    from core.db_connector import get_conn

    conn = get_conn()
    cols = conn.execute("DESCRIBE WIDE_DETAIL").fetchall()
    # cols 格式: [(name, type, ...), ...]

    fixed = [f.model_dump() for f in WIDE_DETAIL_FIXED_FIELDS]
    fixed_names = {f["name"] for f in fixed}

    signals: list[dict] = []
    for row in cols:
        name = row[0]
        dtype = row[1]
        if name in fixed_names:
            continue
        signals.append({
            "name": name,
            "alias_cn": f"信号: {name}",
            "data_type": dtype,
            "source_table": WIDE_DETAIL_TABLE,
            "category": "measure",
            "description": f"信号 {name}",
        })

    all_fields = fixed + signals
    _save_fields_json(all_fields)
    logger.info("字段列表已同步: %d 固定 + %d 信号 = %d 个字段", len(fixed), len(signals), len(all_fields))
    return all_fields


# ============================================================
# 获取字段列表（优先 JSON 缓存，没有则实时同步）
# ============================================================

def _get_all_fields() -> list[dict]:
    fields = _load_fields_json()
    if fields is None:
        try:
            fields = sync_fields_from_wide()
        except Exception as e:
            logger.warning("从宽表同步字段失败: %s，返回纯固定字段", e)
            fields = [f.model_dump() for f in WIDE_DETAIL_FIXED_FIELDS]
    return fields


# ============================================================
# 公共接口
# ============================================================

FIELD_REGISTRY: list[FieldDef] = [FieldDef(**f) for f in _get_all_fields()]

SOURCE_TABLES_CN: dict[str, str] = {
    WIDE_DETAIL_TABLE: WIDE_DETAIL_TABLE_CN,
}


def get_fields_grouped(include_wide_detail: bool = True, wide_top_signals: int = 200) -> list[dict]:
    """字段列表按分组返回：固定字段 + 信号列表"""
    from collections import OrderedDict
    groups: dict[str, dict] = OrderedDict()
    if include_wide_detail:
        fields = _get_all_fields()
        fixed = [f for f in fields if f["name"] in WIDE_DETAIL_FIXED_KEYS]
        dynamic = [f for f in fields if f["name"] not in WIDE_DETAIL_FIXED_KEYS]
        groups["fixed_fields"] = {
            "table_name": "fixed_fields",
            "table_name_cn": "固定字段",
            "fields": fixed[:12],  # 严格 12 个固定字段
        }
        groups["signal_fields"] = {
            "table_name": "signal_fields",
            "table_name_cn": "信号列表",
            "fields": dynamic[:wide_top_signals],
        }
    return list(groups.values())


def get_field_names() -> list[str]:
    return [f["name"] for f in _get_all_fields()]


def get_field(name: str) -> FieldDef | None:
    for f in FIELD_REGISTRY:
        if f.name == name:
            return f
    return None


# ============================================================
# Schema 描述（用于 Agent System Prompt）
# ============================================================

def get_schema_markdown(top_signals: int = 60) -> str:
    """生成 Markdown 格式的 Schema 描述"""
    lines = ["## 明细宽表 WIDE_DETAIL 字段说明\n"]
    lines.append("| 字段名 | 中文别名 | 类型 | 分类 |")
    lines.append("|--------|----------|------|------|")
    for f in WIDE_DETAIL_FIXED_FIELDS:
        lines.append(f"| {f.name} | {f.alias_cn} | {f.data_type} | {f.category} |")

    signals = _get_all_fields()
    dynamic = [s for s in signals if s["name"] not in WIDE_DETAIL_FIXED_KEYS]
    if dynamic:
        lines.append(f"\n> 动态信号列（共 {len(dynamic)} 个，按出现频率 TOP-N 自动展开）：")
        lines.append("| 字段名 | 类型 |")
        lines.append("|--------|------|")
        for s in dynamic[:top_signals]:
            lines.append(f"| {s['name']} | {s['data_type']} |")
        lines.append(f"\n> 说明：信号值可通过 TRY_CAST 转换为数值做聚合。")
    else:
        lines.append("\n> 动态信号列：无数据。")

    return "\n".join(lines)


def get_schema_for_agent(top_signals: int = 60) -> str:
    """生成给 LLM 的 Schema 描述"""
    signals = _get_all_fields()
    dynamic = [s for s in signals if s["name"] not in WIDE_DETAIL_FIXED_KEYS]

    parts = [
        "你的数据来源是明细宽表 WIDE_DETAIL，结构如下：",
        "",
        "## 固定数据字段（12 个）",
        "",
    ]
    for f in WIDE_DETAIL_FIXED_FIELDS:
        parts.append(f"- `{f.name}`（{f.alias_cn}）：{f.data_type}")
    parts.append("")

    if dynamic:
        names_str = ", ".join(f"`{s['name']}`" for s in dynamic[:20])
        if len(dynamic) > 20:
            names_str += f" 等共 {len(dynamic)} 个"
        parts.append(f"## 动态信号列（共 {len(dynamic)} 个，按频率自动展开）")
        parts.append("")
        parts.append(f"信号列名即 SIGNAL_NAME 值，信号值为 VARCHAR 类型（可 TRY_CAST 转 DOUBLE 做数值聚合）。")
        parts.append(f"高频信号示例：{names_str}")
    else:
        parts.append("## 动态信号列：无数据。")

    parts.append("")
    parts.append("## 数据来源")
    parts.append("- 固定 12 字段 + 高频信号列已预构建在明细宽表 WIDE_DETAIL 中")
    parts.append("- 信号列名即 SIGNAL_NAME 值，按出现频率展开为独立列")
    parts.append("")
    parts.append("## 常用分析维度")
    parts.append("- `vehicle_type`（车型）、`rule_name`（规则名称）、`rule_type`（规则类型：统计/报警/事件）、`task`（任务名称）、`person`（人员）")
    parts.append("- 时间：`alarm_time`（报警时间，可用 date_trunc 做时间粒度聚合）、`duration_sec`（持续秒数）")
    parts.append("- 聚合：可用 count(*) 做计数，或对任意信号列用 TRY_CAST 转数值后做 sum/avg/min/max")
    return "\n".join(parts)
