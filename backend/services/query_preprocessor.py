"""用户查询预处理器 — 用规则代码从自然语言中提取结构化图表需求。

输出的 ParsedChartRequest 注入到 LLM prompt 中，
让 LLM 只需做 "结构化描述 → PivotConfig" 的映射，不必从自由文本中理解语义。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any


class ParsedChartRequest:
    """预解析的结构化图表请求

    所有字段均由规则代码从用户输入中提取，
    LLM 只需参照此结构生成 PivotConfig。
    """

    def __init__(self) -> None:
        self.explicit_chart_type: str | None = None
        self.time_field: str | None = None
        self.time_range: dict[str, str] | None = None
        self.group_by_fields: list[str] = []
        self.legend_field: str | None = None
        self.metrics: list[dict[str, str]] = []
        self.task_ref: str | None = None
        self.rule_name: str | None = None

    def is_empty(self) -> bool:
        return not any([
            self.explicit_chart_type, self.time_field,
            self.time_range, self.group_by_fields,
            self.legend_field, self.metrics,
            self.task_ref, self.rule_name,
        ])

    def to_prompt_section(self) -> str:
        """渲染为 LLM prompt 中可以嵌入的段落"""
        if self.is_empty():
            return ""

        lines = [
            "# Parsed User Request（已从原文解析，请严格参照生成 PivotConfig）\n"
        ]
        if self.explicit_chart_type:
            lines.append(f"- 图表类型: {self.explicit_chart_type}（用户明确要求，必须严格使用）")
        if self.time_range:
            tr = self.time_range
            lines.append(
                f"- 时间筛选: 字段={self.time_field or '自动识别'}, "
                f"范围={tr.get('start', '')}~{tr.get('end', '')}, "
                f"聚合粒度={tr.get('granularity', '原始')}"
            )
        if self.group_by_fields:
            items = "、".join(self.group_by_fields)
            lines.append(f"- 行维度（axes）: {items}")
        if self.legend_field:
            lines.append(f"- 图例/列维度（legend）: {self.legend_field}")
        if self.metrics:
            for m in self.metrics:
                lines.append(
                    f"- 指标: 度量名={m.get('label', '')}, 聚合={m.get('aggregation', 'source')}"
                )
        if self.task_ref:
            lines.append(f"- 引用任务: {self.task_ref}（需映射到 TASK_ID 筛选条件）")
        if self.rule_name:
            lines.append(f"- 引用规则: {self.rule_name}")

        return "\n".join(lines)


# ============================================================
# 规则引擎
# ============================================================

_CHART_TYPE_MAP = {
    "柱状": "bar", "柱状图": "bar",
    "折线": "line", "折线图": "line",
    "饼图": "pie",
    "雷达": "radar", "雷达图": "radar",
    "散点": "point", "散点图": "point",
    "面积": "area", "面积图": "area",
}

_GRANULARITY_MAP = {
    "每天": "day", "每日": "day", "按天": "day", "逐天": "day",
    "每周": "week", "按周": "week",
    "每月": "month", "按月": "month",
    "每年": "year", "逐年": "year",
}


def _extract_chart_type(pq: ParsedChartRequest, text: str) -> None:
    for kw, ct in _CHART_TYPE_MAP.items():
        if kw in text:
            pq.explicit_chart_type = ct
            return


def _extract_time_range(pq: ParsedChartRequest, text: str) -> None:
    patterns = [
        r"从?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\s*[~至到\-]\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|[0-1]?\d[-/.]\d{1,2})",
        r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\s*[至到~\-]\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|[0-1]?\d[-/.]\d{1,2})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            start = m.group(1).replace("/", "-").replace(".", "-")
            end_raw = m.group(2)
            if end_raw.replace("-", "/").replace(".", "/").count("/") == 1:
                year = start[:4]
                end = f"{year}-{end_raw.replace('/', '-').replace('.', '-')}"
            else:
                end = end_raw.replace("/", "-").replace(".", "-")
            pq.time_range = {"start": start, "end": end, "granularity": "day"}
            pq.time_field = "报警日期"
            break

    for kw, gran in _GRANULARITY_MAP.items():
        if kw in text:
            if pq.time_range:
                pq.time_range["granularity"] = gran
            break

    # 相对时间范围（如"最近一周"、"最近30天"）
    if pq.time_range is None:
        relative_patterns = [
            (r"最近(\d+)天", "day", lambda n: timedelta(days=n)),
            (r"最近(\d+)周", "week", lambda n: timedelta(weeks=n)),
            (r"最近(\d+)个月", "month", lambda n: timedelta(days=n * 30)),
            (r"最近一周", "day", lambda _: timedelta(weeks=1)),
            (r"最近一个月", "day", lambda _: timedelta(days=30)),
            (r"近(\d+)天", "day", lambda n: timedelta(days=n)),
            (r"近一周", "day", lambda _: timedelta(weeks=1)),
            (r"本月", "month", None),
        ]
        for pat, gran, delta_fn in relative_patterns:
            m = re.search(pat, text)
            if m:
                today = datetime.now()
                if delta_fn:
                    n = int(m.group(1)) if m.lastindex and m.group(1) else 1
                    start = (today - delta_fn(n)).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")
                else:
                    start = today.replace(day=1).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")
                pq.time_range = {"start": start, "end": end, "granularity": gran}
                pq.time_field = "报警日期"
                break


def _extract_legend(pq: ParsedChartRequest, text: str) -> None:
    patterns = [
        r"用(.+?)(做|作为|为)(图例|分组)",
        r"按(.+?)(做|作为|为)?(图例|分组|区分)",
        r"以(.+?)(为)?(图例|分组)",
        r"按(.+?)统计",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            field = m.group(1).strip()
            if "规则" in field:
                pq.legend_field = "规则名称"
            elif "车型" in field or "车" in field:
                pq.legend_field = "车型"
            elif "任务" in field:
                pq.legend_field = "任务名称"
            elif "类型" in field or "分类" in field:
                pq.legend_field = "规则类型"
            else:
                pq.legend_field = field
            return


def _extract_metrics(pq: ParsedChartRequest, text: str) -> None:
    if re.search(r"报警(次数|数量|总数|量|频次)", text):
        pq.metrics.append({"label": "报警次数", "aggregation": "count"})

    # 时长相关（含独立关键词）
    if "时长" in text or "持续时间" in text or "最长时间" in text or "最短时间" in text or "平均时长" in text:
        label = "平均时长"
        agg = "avg"
        if "最大" in text or "最长" in text:
            label, agg = "最长时间", "max"
        elif "最小" in text or "最短" in text:
            label, agg = "最短时间", "min"
        pq.metrics.append({"label": label, "aggregation": agg})


def _map_value_field(field: str) -> dict[str, str]:
    """将用户描述的纵轴字段映射为内部指标名"""
    if "报警" in field and ("次数" in field or "数量" in field or "频次" in field or "总数" in field):
        return {"label": "报警时间", "aggregation": "count"}
    if "时长" in field or "持续时间" in field or "时间" in field:
        if "平均" in field:
            return {"label": "平均时长", "aggregation": "avg"}
        if "最大" in field or "最长" in field:
            return {"label": "最长时间", "aggregation": "max"}
        if "最小" in field or "最短" in field:
            return {"label": "最短时间", "aggregation": "min"}
        return {"label": "平均时长", "aggregation": "avg"}
    if "占比" in field or "比例" in field:
        return {"label": "占比", "aggregation": "count"}
    return {"label": field, "aggregation": "source"}


def _extract_group_by(pq: ParsedChartRequest, text: str) -> None:
    # 横轴/X轴/横坐标 → 归到 axes
    _axes_patterns = [
        (r'(?:横轴|x轴|X轴|横坐标)[:：=为是]?\s*(?!信号)(.+?)(?=[，,。、\s]|$)', 1),
        (r'以(.+?)为(?:横轴|x轴|X轴|横坐标)', 1),
    ]
    for pat, group_idx in _axes_patterns:
        m = re.search(pat, text)
        if m:
            field = m.group(group_idx).strip().lstrip("=：:，,。 ")
            if field and field not in pq.group_by_fields:
                pq.group_by_fields.append(field)

    # 信号[...] / 信号【...】 / 信号“...” → 解析出信号名，每个独立加到 axes
    _signal_patterns = [
        r'信号\[([^\]]+?)\]',        # 信号[Hev,Hds]
        r'信号【([^】]+?)】',        # 信号【Hev】
        r'信号[“"]([^”"]+?)[”"]',   # 信号"Hev,Hds"
        r'信号（([^）]+?)）',        # 信号（Hev）
    ]
    for sp in _signal_patterns:
        for m in re.finditer(sp, text):
            content = m.group(1).strip()
            # 按分隔符拆分：逗号/顿号/斜杠/反斜杠/空白
            names = re.split(r'[,，、/\\\\\s]+', content)
            for name in names:
                name = name.strip()
                if name and name not in pq.group_by_fields:
                    pq.group_by_fields.append(name)

    # 纵轴/Y轴/竖轴 → 归到 values/metrics
    _values_patterns = [
        (r'(?:纵轴|y轴|Y轴|竖轴)[:：=为是]?\s*(.+?)(?=[，,。、\s]|$)', 1),
        (r'以(.+?)为(?:纵轴|y轴|Y轴|竖轴|纵坐标)', 1),
    ]
    for pat, group_idx in _values_patterns:
        m = re.search(pat, text)
        if m:
            field = m.group(group_idx).strip().lstrip("=：:，,。 ")
            # 同样截断到逗号前，避免捕获后半句
            cut_pos = len(field)
            for sep in ["，", ",", "、"]:
                pos = field.find(sep)
                if 0 < pos < cut_pos:
                    cut_pos = pos
            field = field[:cut_pos].strip()
            if field:
                # 映射到已知指标名
                mapped = _map_value_field(field)
                if not any(me.get("label") == mapped["label"] for me in pq.metrics):
                    pq.metrics.append(mapped)

    if re.search(r"(每天|每日|按天|逐天)", text):
        pq.group_by_fields.append("报警日期")
    if re.search(r"各车型|按车型|分车型", text):
        pq.group_by_fields.append("车型")
    if re.search(r"各任务|按任务", text):
        pq.group_by_fields.append("任务名称")
    if re.search(r"各规则|按规则", text):
        if "规则名称" not in pq.group_by_fields:
            pq.group_by_fields.append("规则名称")


def _extract_task(pq: ParsedChartRequest, text: str) -> None:
    # [任务名_ID] 格式
    m = re.search(r'\[(.+?)_(\d+)\]', text)
    if m:
        pq.task_ref = m.group(1).strip()
        return
    # TASK_ID=123 或 task:123
    m = re.search(r'(?:TASK[_\s]?ID|task[_\s]?id)\s*[=:]\s*(\d+)', text)
    if m:
        pq.task_ref = f"TASK_ID={m.group(1)}"
        return
    # "针对/关联/属于/在 任务：名称" 的显式引用（排除"各任务""按任务"等分组语义）
    m = re.search(r'(?:针对|关联|属于|在|分析)\s*任务\s*[：:]\s*(.+?)(?:[，,。\s]|$)', text)
    if m:
        pq.task_ref = m.group(1).strip()


def preprocess_chart_query(text: str) -> ParsedChartRequest:
    """预处理图表查询：规则代码提取 → 结构化中间语言"""
    pq = ParsedChartRequest()
    _extract_chart_type(pq, text)
    _extract_time_range(pq, text)
    _extract_legend(pq, text)
    _extract_metrics(pq, text)
    _extract_group_by(pq, text)
    _extract_task(pq, text)
    return pq
