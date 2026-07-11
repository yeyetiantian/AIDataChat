"""字段注册表

字段信息从 SQLite（ai_data.db）读取。
用于：
1. 前端字段列表展示
2. LangGraph Agent 的 Schema 注入
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("field_registry")


class FieldDef(BaseModel):
    """字段定义"""
    name: str = Field(..., description="字段名")
    alias_cn: str = Field(..., description="中文别名")
    data_type: str = Field(..., description="数据类型")
    description: str = Field("", description="业务说明")
    example_values: Optional[str] = Field(None, description="示例值")
    fixed: bool = Field(False, description="是否为固定字段")
    category: str = Field("dimension", description="分类")


def _get_all_fields() -> list[dict]:
    """从数据库获取所有字段"""
    from core.chat_db import list_fields
    try:
        return list_fields()
    except Exception as e:
        logger.warning("从数据库读取字段失败: %s", e)
        return []


def get_fixed_field_names() -> set[str]:
    """从数据库获取固定字段名集合"""
    from core.chat_db import get_fixed_field_names
    try:
        return get_fixed_field_names()
    except Exception:
        return set()


def get_field_names() -> list[str]:
    """从数据库获取所有字段名"""
    from core.chat_db import get_field_names
    try:
        return get_field_names()
    except Exception:
        return []


def get_fields_grouped() -> list[dict]:
    """字段列表按分组返回：固定字段 + 信号列表"""
    fields = _get_all_fields()
    fixed = [f for f in fields if f.get("fixed")]
    dynamic = [f for f in fields if not f.get("fixed")]

    from collections import OrderedDict
    groups: dict[str, dict] = OrderedDict()
    groups["fixed_fields"] = {
        "table_name": "fixed_fields",
        "table_name_cn": "固定字段",
        "fields": fixed,
    }
    groups["signal_fields"] = {
        "table_name": "signal_fields",
        "table_name_cn": "信号列表",
        "fields": dynamic,
    }
    return list(groups.values())


def get_schema_markdown() -> str:
    """生成 Markdown 格式的 Schema 描述"""
    lines = ["## 字段说明\n"]
    lines.append("| 字段名 | 中文别名 | 类型 | 分类 |")
    lines.append("|--------|----------|------|------|")

    fields = _get_all_fields()
    fixed = [f for f in fields if f.get("fixed")]
    dynamic = [f for f in fields if not f.get("fixed")]

    for f in fixed:
        lines.append(f"| {f['name']} | {f['alias_cn']} | {f['data_type']} | {f.get('category', 'dimension')} |")

    if dynamic:
        lines.append(f"\n> 动态信号列（共 {len(dynamic)} 个）：")
        lines.append("| 字段名 | 类型 |")
        lines.append("|--------|------|")
        for s in dynamic:
            lines.append(f"| {s['name']} | {s['data_type']} |")
        lines.append("\n> 说明：信号值可通过 TRY_CAST 转换为数值做聚合。")
    else:
        lines.append("\n> 动态信号列：无数据。")

    return "\n".join(lines)


def get_schema_for_agent(top_signals: int = 60) -> str:
    """生成给 LLM 的 Schema 描述"""
    fields = _get_all_fields()
    fixed = [f for f in fields if f.get("fixed")]
    dynamic = [f for f in fields if not f.get("fixed")]

    parts = [
        "你的数据支持以下字段：",
        "",
        "## 固定数据字段",
        "",
    ]
    for f in fixed:
        parts.append(f"- `{f['name']}`（{f['alias_cn']}）：{f['data_type']}")
    parts.append("")

    if dynamic:
        names_str = ", ".join(f"`{s['name']}`" for s in dynamic[:200])
        if len(dynamic) > 200:
            names_str += f" 等共 {len(dynamic)} 个"
        parts.append(f"## 动态信号列（共 {len(dynamic)} 个）")
        parts.append("")
        parts.append("信号值为 VARCHAR 类型，在聚合（sum/avg/min/max）时系统自动转换为数值。")
        parts.append(f"高频信号示例：{names_str}")
    else:
        parts.append("## 动态信号列：无数据。")

    parts.append("")
    parts.append("## 不确定字段的处理规则")
    parts.append("除上述固定字段外的所有列名均为动态信号列。")
    parts.append("如果你遇到不确定或不认识的字段名，一律归类为动态信号列，使用其原始列名即可。")
    parts.append("")
    parts.append("## 数据来源")
    parts.append("- 所有字段经底层自动关联拼装，你只需直接引用字段名即可。")
    parts.append("")
    return "\n".join(parts)
