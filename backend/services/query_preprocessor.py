from __future__ import annotations
import re
import logging
from datetime import datetime, timedelta
from typing import Any, List, Tuple, Set, Optional

# ====================== 全局常量统一管理（消除魔法字符串）======================
BRACKET_OPEN = r'[\[【({]'
BRACKET_CLOSE = r'[\]】)}]'
BRACKET_PATTERN = re.compile(rf'({BRACKET_OPEN})(.*?)({BRACKET_CLOSE})')
SPLIT_SEP_PAT = re.compile(r'[，,、]')

AXIS_KEYWORDS = ("横轴", "x轴", "X轴", "横坐标", "行维度")
VALUE_KEYWORDS = ("纵轴", "y轴", "Y轴", "竖轴", "纵坐标", "列维度")
LEGEND_KEYWORDS = ("图例", "分组", "区分")

CHART_TYPE_MAP = {
    "柱状": "bar", "柱状图": "bar",
    "折线": "line", "折线图": "line",
    "饼图": "pie",
    "雷达": "radar", "雷达图": "radar",
    "散点": "point", "散点图": "point",
    "面积": "area", "面积图": "area", "区域": "area", "区域图": "area",
}
GRANULARITY_MAP = {
    "每天": "day", "每日": "day", "按天": "day", "逐天": "day",
    "每周": "week", "按周": "week",
    "每月": "month", "按月": "month",
    "每年": "year", "逐年": "year",
}

# 日志工具
logger = logging.getLogger("chart_preprocessor")

# ====================== 通用工具函数（统一封装、增加校验）======================
def extract_all_bracket_blocks(text: str) -> List[Tuple[str, str, int]]:
    """提取所有完整括号块 (完整括号文本, 内部内容, 起始下标)"""
    res = []
    for match in BRACKET_PATTERN.finditer(text):
        full_block = match.group(0)
        inner = match.group(2).strip()
        start_idx = match.start()
        res.append((full_block, inner, start_idx))
    return res

def split_bracket_fields(inner_text: str) -> List[str]:
    """拆分括号内字段，过滤空字符串"""
    raw_parts = SPLIT_SEP_PAT.split(inner_text)
    parts = [p.strip() for p in raw_parts if p.strip()]
    return parts

def unique_append(target_list: List[str], items: List[str]) -> None:
    """去重追加字符串列表"""
    exist = set(target_list)
    for item in items:
        if item and item not in exist:
            target_list.append(item)
            exist.add(item)

def unique_append_metric(target_metrics: List[dict], mapped: dict) -> None:
    """指标字典去重追加"""
    label = mapped.get("label", "")
    if not any(m["label"] == label for m in target_metrics):
        target_metrics.append(mapped)

def find_all_matches(pattern: str, text: str, group_idx: int = 1) -> List[str]:
    pat = re.compile(pattern)
    results = []
    for m in pat.finditer(text):
        try:
            val = m.group(group_idx).strip()
            if val:
                results.append(val)
        except IndexError:
            continue
    return results

def is_signal_bracket(full_text: str, block_start: int, full_text_all: str) -> bool:
    """判断括号是否属于 信号[]"""
    prefix = full_text_all[max(0, block_start - 6): block_start]
    return "信号" in prefix

# ====================== 数据模型 ======================
class ParsedChartRequest:
    def __init__(self) -> None:
        self.explicit_chart_type: Optional[str] = None
        self.time_field: Optional[str] = None
        self.time_range: Optional[dict[str, str]] = None
        self.group_by_fields: List[str] = []
        self.legend_field: Optional[str] = None
        self.metrics: List[dict[str, str]] = []
        self.task_ref: Optional[str] = None
        self.rule_name: Optional[str] = None

    def is_empty(self) -> bool:
        return not any([
            self.explicit_chart_type, self.time_field,
            self.time_range, self.group_by_fields,
            self.legend_field, self.metrics,
            self.task_ref, self.rule_name,
        ])

    def to_prompt_section(self) -> str:
        if self.is_empty():
            return ""
        lines = ["# Parsed User Request（已从原文解析，请严格参照生成 PivotConfig）\n"]
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
            lines.append(f"- 图例（legend）: {self.legend_field}")
        for m in self.metrics:
            lines.append(f"- 指标（values）: 度量名={m.get('label', '')}, 聚合={m.get('aggregation', 'source')}")
        if self.task_ref:
            lines.append(f"- 引用任务: {self.task_ref}")
        return "\n".join(lines)

# ====================== 字段映射工具 ======================
def _map_value_field(field: str) -> dict[str, str]:
    if "报警" in field and ("次数" in field or "数量" in field or "频次" in field or "总数" in field):
        return {"label": "报警次数", "aggregation": "count"}
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

# ====================== 各提取器拆分（解耦，单独可复用）======================
def extract_chart_type(pq: ParsedChartRequest, text: str) -> None:
    for kw, ct in CHART_TYPE_MAP.items():
        if kw in text:
            pq.explicit_chart_type = ct
            logger.debug(f"识别图表类型 {kw} → {ct}")
            return

def extract_time_range(pq: ParsedChartRequest, text: str) -> None:
    abs_patterns = [
        r"从?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\s*[~至到\-]\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|[0-1]?\d[-/.]\d{1,2})",
        r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\s*[至到~\-]\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|[0-1]?\d[-/.]\d{1,2})",
    ]
    for pat in abs_patterns:
        m = re.search(pat, text)
        if m:
            start = m.group(1).replace("/", "-").replace(".", "-")
            end_raw = m.group(2)
            if end_raw.replace("-", "/").replace(".", "/").count("/") == 1:
                end = f"{start[:4]}-{end_raw.replace('/', '-').replace('.', '-')}"
            else:
                end = end_raw.replace("/", "-").replace(".", "-")
            pq.time_range = {"start": start, "end": end, "granularity": "day"}
            pq.time_field = "报警日期"
            logger.debug(f"识别绝对时间范围 {start} ~ {end}")
            break
    for kw, gran in GRANULARITY_MAP.items():
        if kw in text and pq.time_range:
            pq.time_range["granularity"] = gran
            logger.debug(f"识别时间粒度 {kw} → {gran}")
            break
    if pq.time_range is None:
        rel_patterns = [
            (r"最近(\d+)天", "day", lambda n: timedelta(days=n)),
            (r"最近(\d+)周", "week", lambda n: timedelta(weeks=n)),
            (r"最近(\d+)个月", "month", lambda n: timedelta(days=n * 30)),
            (r"最近一周", "day", lambda _: timedelta(weeks=1)),
            (r"最近一个月", "day", lambda _: timedelta(days=30)),
            (r"近(\d+)天", "day", lambda n: timedelta(days=n)),
            (r"近一周", "day", lambda _: timedelta(weeks=1)),
            (r"本月", "month", None),
        ]
        today = datetime.now()
        for pat, gran, delta_fn in rel_patterns:
            m = re.search(pat, text)
            if m:
                if delta_fn:
                    n = int(m.group(1)) if m.lastindex and m.group(1) else 1
                    start = (today - delta_fn(n)).strftime("%Y-%m-%d")
                else:
                    start = today.replace(day=1).strftime("%Y-%m-%d")
                end = today.strftime("%Y-%m-%d")
                pq.time_range = {"start": start, "end": end, "granularity": gran}
                pq.time_field = "报警日期"
                logger.debug(f"识别相对时间 {pat} → {start} ~ {end}")
                break

def extract_legend(pq: ParsedChartRequest, text: str) -> None:
    patterns = [
        r"用(.+?)(做|作为|为)(图例|分组)",
        r"按(.+?)(做|作为|为)?(图例|分组|区分)",
        r"以(.+?)(为)?(图例|分组)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            raw = m.group(1).strip()
            # 兼容括号内信号作为图例
            blocks = extract_all_bracket_blocks(raw)
            if blocks:
                inner = blocks[0][1]
                fields = split_bracket_fields(inner)
                pq.legend_field = ",".join(fields)
            else:
                if "规则" in raw:
                    pq.legend_field = "规则名称"
                elif "车型" in raw or "车" in raw:
                    pq.legend_field = "车型"
                elif "任务" in raw:
                    pq.legend_field = "任务名称"
                elif "类型" in raw or "分类" in raw:
                    pq.legend_field = "规则类型"
                else:
                    pq.legend_field = raw
            logger.debug(f"识别图例 {pq.legend_field}")
            return

def extract_task(pq: ParsedChartRequest, text: str) -> None:
    all_blocks = extract_all_bracket_blocks(text)
    for full_block, bracket_text, start_idx in all_blocks:
        if is_signal_bracket(full_block, start_idx, text):
            continue
        task_match = re.search(r'(.+?)_\d+(?:_\d+)*$', bracket_text)
        if task_match:
            pq.task_ref = task_match.group(1).strip()
            logger.debug(f"从括号识别任务 {pq.task_ref}")
            return
    m = re.search(r'(?:TASK[_\s]?ID|task[_\s]?id)\s*[=:]\s*(\d+)', text)
    if m:
        pq.task_ref = f"TASK_ID={m.group(1)}"
        logger.debug(f"识别数字任务ID {pq.task_ref}")
        return
    m = re.search(r'(?:针对|关联|属于|在|分析)(?!按|各|每个)\s*任务\s*[：:]\s*(.+?)(?=[，,。、]|$)', text)
    if m:
        raw_task = m.group(1).strip()
        clean_task = raw_task.lstrip("=：:，,。、").rstrip("=：:，,。、")
        if clean_task:
            pq.task_ref = clean_task
            logger.debug(f"自然语言识别任务 {pq.task_ref}")

def extract_signal_fields(pq: ParsedChartRequest, text: str) -> None:
    """统一信号提取入口，兼容前置横轴/纵轴、后置句式、裸信号"""
    # 1. 前置句式：横轴信号[...] / 纵轴信号[...]
    axis_pat = rf'(?:{"|".join(AXIS_KEYWORDS)})[:：=为是]?\s*信号\s*({BRACKET_OPEN}.*?{BRACKET_CLOSE})'
    axis_brackets = find_all_matches(axis_pat, text, 1)
    for bracket_str in axis_brackets:
        inner = BRACKET_PATTERN.search(bracket_str).group(2).strip()
        fields = split_bracket_fields(inner)
        unique_append(pq.group_by_fields, fields)
        logger.debug(f"横轴提取字段 {fields}")

    val_pat = rf'(?:{"|".join(VALUE_KEYWORDS)})[:：=为是]?\s*信号\s*({BRACKET_OPEN}.*?{BRACKET_CLOSE})'
    val_brackets = find_all_matches(val_pat, text, 1)
    for bracket_str in val_brackets:
        inner = BRACKET_PATTERN.search(bracket_str).group(2).strip()
        fields = split_bracket_fields(inner)
        for f in fields:
            unique_append_metric(pq.metrics, _map_value_field(f))
        logger.debug(f"纵轴提取指标 {fields}")

    # 2. 后置句式：[xxx] 作为横轴
    post_axis_pat = rf'({BRACKET_OPEN}.*?{BRACKET_CLOSE})\s*(?:作为|为|是)\s*(?:{"|".join(AXIS_KEYWORDS)})'
    post_axis_matches = find_all_matches(post_axis_pat, text, 1)
    for bracket_str in post_axis_matches:
        inner = BRACKET_PATTERN.search(bracket_str).group(2).strip()
        fields = split_bracket_fields(inner)
        unique_append(pq.group_by_fields, fields)
        logger.debug(f"后置横轴提取字段 {fields}")

    post_val_pat = rf'({BRACKET_OPEN}.*?{BRACKET_CLOSE})\s*(?:作为|为|是)\s*(?:{"|".join(VALUE_KEYWORDS)})'
    post_val_matches = find_all_matches(post_val_pat, text, 1)
    for bracket_str in post_val_matches:
        inner = BRACKET_PATTERN.search(bracket_str).group(2).strip()
        fields = split_bracket_fields(inner)
        for f in fields:
            unique_append_metric(pq.metrics, _map_value_field(f))
        logger.debug(f"后置纵轴提取指标 {fields}")

    # 3. 裸信号[]：无横纵轴标识，全部归入values
    all_blocks = extract_all_bracket_blocks(text)
    for full_block, inner, start_idx in all_blocks:
        if not is_signal_bracket(full_block, start_idx, text):
            continue
        # 判断括号前方是否已有横纵轴关键词（已处理过的跳过）
        prefix_text = text[:start_idx]
        has_axis = any(k in prefix_text for k in AXIS_KEYWORDS)
        has_val = any(k in prefix_text for k in VALUE_KEYWORDS)
        if has_axis or has_val:
            continue
        fields = split_bracket_fields(inner)
        for f in fields:
            unique_append_metric(pq.metrics, _map_value_field(f))
        logger.debug(f"裸信号提取指标 {fields}")

# ====================== 统一入口 ======================
def preprocess_chart_query(text: str) -> ParsedChartRequest:
    pq = ParsedChartRequest()
    try:
        extract_chart_type(pq, text)
        extract_time_range(pq, text)
        extract_legend(pq, text)
        extract_task(pq, text)
        extract_signal_fields(pq, text)
    except Exception as e:
        logger.error(f"预处理解析异常 text={text[:200]} err={str(e)}", exc_info=True)
    return pq