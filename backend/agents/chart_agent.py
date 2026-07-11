"""图表分析子 Agent — analyze → validate → execute → format_reply

数据流：
  analyze（LLM 生成 PivotConfig）→ validate（校验配置）→
    通过 → execute（调用 Pivot API）→ format_reply
    失败 → 回流 analyze 重试（最多 1 次）
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, TypedDict

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel

from agents.llm_utils import (
    is_private_provider,
    get_llm,
    get_structured_llm,
    try_parse_json,
    save_trace_log,
    TraceCollector,
    SpanNode,
)
from core.field_registry import get_schema_for_agent, get_fixed_field_names
from llm import get_auth_headers
from models import PivotConfig, PivotResponse

logger = logging.getLogger("chart_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Structured Output 模型
# ============================================================

class QuestionOption(BaseModel):
    """问卷选项"""
    label: str = ""
    value: str = ""
    recommended: bool = False


class QuestionItem(BaseModel):
    """问卷问题 — LLM 发起交互式需求收集"""
    id: str = ""
    question: str = ""
    type: str = "select"  # select / multi_select / input
    options: list[QuestionOption] = []
    placeholder: str = ""
    required: bool = True


class ChartItem(BaseModel):
    """单个图表配置"""
    title: str = ""
    pivot_config: PivotConfig
    chart_type: str = "bar"


class AgentOutput(BaseModel):
    """LLM 结构化输出"""
    intent: str
    reply: str
    charts: list[ChartItem] = []
    suggestions: list[str] = []
    ask_questions: list[QuestionItem] = []


# ============================================================
# 全局缓存
# ============================================================

_schema_cache: str | None = None
_chart_system_prompt: str | None = None











def _get_schema_text() -> str:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = get_schema_for_agent(top_signals=60)
    return _schema_cache


def _get_chart_system_prompt() -> str:
    global _chart_system_prompt
    if _chart_system_prompt is not None:
        return _chart_system_prompt

    schema = _get_schema_text()
    _chart_system_prompt = f"""# Role
你是数据分析助手。根据用户自然语言需求，生成数据透视图表配置（PivotConfig）。

# Available Fields
{schema}

# Output Structure
你输出的是 AgentOutput 结构体：
- intent: "chart"
- reply: 回复用户的文字
- charts: 图表配置列表
- suggestions: 建议用户追问的问题（3 个）
- ask_questions: 需要用户进一步输入时的问卷列表（交互式需求收集）

每个 chart 包含：
- title: 图表标题
- pivot_config: PivotConfig JSON
- chart_type: 图表类型

# Interactive Q&A (Ask Questions)
当你需要向用户收集更多信息才能生成图表时，使用 ask_questions 字段。
输出一个或多个 QuestionItem，每个包含：
- id: 问题唯一标识（如 "chart_count"、"task_id"、"chart_direction"）
- question: 向用户展示的问题文本
- type: 交互类型（select=单选, multi_select=多选, input=文本输入）
- options: select/multi_select 类型的选项列表
- required: 是否必填

## ask_questions 使用场景（非常重要）
**规则：如果用户没有明确说出以下信息，必须先输出 ask_questions 收集，不能直接生成图表：**
1. 用户说 "帮我创建一个看板"（没有提供具体图表）-> **必须**输出 ask_questions 询问：看板名称、图表数量、关联任务
2. 用户说 "帮我分析一个报表"（没有说分析方向）-> **必须**输出 ask_questions 询问分析维度和图表类型
3. 用户的需求明确（如 "各车型报警次数"）-> 不需要 ask_questions，直接输出 charts
4. 用户提供了具体分析方向（如 "各车型报警次数和报警趋势"）-> 不需要 ask_questions，直接生成对应图表
5. 用户消息包含 [问卷提交] 前缀 -> 这是用户回答了你的问题，**不要**再输出 ask_questions，直接生成图表

## 示例
用户："帮我创建一个看板"
回复：
  reply: "好的，我需要了解一些信息来创建看板："
  ask_questions: [
    {{
      "id": "board_name", "question": "看板名称是什么？", "type": "input", "placeholder": "如：车辆违规监控看板", "required": true
    }},
    {{
      "id": "chart_count", "question": "需要包含几个图表？", "type": "select", "options": [
        {{"label": "2个", "value": "2"}}, {{"label": "3个", "value": "3", "recommended": true}},
        {{"label": "4个", "value": "4"}}, {{"label": "5个", "value": "5"}}, {{"label": "6个", "value": "6"}}
      ], "required": true
    }},
    {{
      "id": "task_id", "question": "需要关联哪个任务？", "type": "select", "options": [
        {{"label": "不关联任务", "value": "", "recommended": true}},
        {{"label": "TASK_ID=1: xxx", "value": "1"}}, {{"label": "TASK_ID=2: xxx", "value": "2"}}
      ], "required": false
    }}
  ]
  charts: []  # 不输出图表
  suggestions: []

用户回答了问卷后，请根据用户提供的看板名称、图表数量等信息和用户之前说过的每张图表的具体方向，**直接生成合理的图表配置**。
每个图表使用不同的分析维度和图表类型，确保多样性。

PivotConfig 核心 4 属性：
1. filters → SQL WHERE（筛选器）
2. axes → GROUP BY（行维度）
3. legend → PIVOT ON（列维度/图例）
4. values → 聚合值

# Field Specifications

## axes（行维度，必填，至少 1 个）
- field: 字段名（必填，从 Available Fields 选择）
- alias: 显示别名（必填）
- aggregation: source / day / week / month / year（仅时间字段可用）

## legend（列维度/图例，默认不指定）
- field: 字段名（必填）
- alias: 显示别名（必填）

## values（聚合值，必填，至少 1 个）
- field: 字段名（必填）
- aggregation: source / count / sum / avg / min / max

## filters（筛选条件，可选）
- field: 字段名（必填），只能用 Available Fields 中的固定字段
- value: 必须是数组
- op: lt / gt / gte / lte / between / in

# Constraints
- axes 至少 1 个，values 至少 1 个
- 所有 field 必须来自 Available Fields
- 不确定或不认识的字段名 → 归类为动态信号列

# Examples
{{"intent": "chart", "reply": "各车型的报警次数如下：", "charts": [
  {{ "title": "各车型报警次数", "pivot_config": {{ "filters": [], "axes": [{{"field": "vehicle_type", "alias": "车型"}}], "values": [{{"field": "alarm_time", "aggregation": "source", "alias": "报警次数"}}], "having": [], "limit": 1000 }}, "chart_type": "bar" }}
]}}"""

    # === 追加任务/规则上下文 ===
    from core.chat_db import list_all_tasks, list_all_rules
    try:
        tasks = list_all_tasks(limit=60)
        rules = list_all_rules(limit=120)
        ext = ["\n## Available Tasks & Rules\n你可以根据用户需求，引用以下任务和规则来生成图表。\n"]
        ext.append("### 任务列表\n")
        for t in tasks:
            ext.append(f"- TASK_ID={t['TASK_ID']}: {t.get('TASK_NAME', '')}\n")
        ext.append("\n### 规则列表\n")
        for r in rules:
            ext.append(f"- RULE_ID={r['TASK_RULE_ID']}: {r.get('RULE_NAME', '')} (关联 TASK_ID={r.get('TASK_ID', '')})\n")
        _chart_system_prompt += "".join(ext)
    except Exception:
        pass  # 如果外部数据表不存在，跳过

    return _chart_system_prompt



# ---- Agent State ----
class ChartState(TypedDict):
    """图表分析状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    reply: str
    charts: list[dict[str, Any]]
    suggestions: list[str]
    error: str | None
    analyze_retry_count: int
    validation_error: str | None

    trace_collector: TraceCollector | None
    trace_span: SpanNode | None

    # 交互式问卷相关
    ask_questions: list[dict[str, Any]]
    pending_step: str | None  # "awaiting_questions" / None


# ---- 工具函数 ----

_FILTER_VALID_OPS = {"lt", "gt", "gte", "lte", "between", "in"}
_fixed_field_names: set[str] | None = None


def _get_fixed_names() -> set[str]:
    global _fixed_field_names
    if _fixed_field_names is None:
        _fixed_field_names = get_fixed_field_names()
    return _fixed_field_names


def _deep_normalize_chart(chart: dict[str, Any]) -> dict[str, Any]:
    pc = chart.get("pivot_config")
    if not pc or not isinstance(pc, dict):
        return chart

    fixed_names = _get_fixed_names()

    # filters 处理
    filters = pc.get("filters")
    if isinstance(filters, list) and len(filters) > 0:
        cleaned: list[dict] = []
        for f in filters:
            if not isinstance(f, dict):
                continue
            if not f.get("field") or f["field"] not in fixed_names:
                continue
            val = f.get("value")
            if not isinstance(val, list):
                val = [val] if val is not None else []
            converted: list = []
            for v in val:
                if isinstance(v, str):
                    try:
                        if "." in v or v.isdigit():
                            converted.append(float(v) if "." in v else int(v))
                        else:
                            converted.append(v)
                    except (ValueError, TypeError):
                        converted.append(v)
                else:
                    converted.append(v)
            f["value"] = converted
            op = f.get("op", "in")
            if op not in _FILTER_VALID_OPS:
                op = "in"
            f["op"] = op
            cleaned.append(f)
        pc["filters"] = cleaned

    # legend 处理
    legend = pc.get("legend")
    values = pc.get("values", [])
    value_fields: set[str] = set()
    if isinstance(values, list):
        for v in values:
            if isinstance(v, dict) and v.get("field"):
                value_fields.add(v["field"])

    if isinstance(legend, list) and len(legend) > 0 and isinstance(values, list):
        pc["legend"] = [
            l for l in legend
            if isinstance(l, dict) and l.get("field")
            and (l["field"] in fixed_names or l["field"] in value_fields)
        ]

    # order_by 处理
    ob = pc.get("order_by", [])
    if isinstance(ob, list) and len(ob) > 0:
        pc["order_by"] = [
            o for o in ob
            if isinstance(o, dict) and o.get("field") and o["field"] in value_fields
        ]

    return chart


def _normalize_charts_from_output(response: AgentOutput) -> list[dict[str, Any]]:
    if response.charts:
        charts = [c.model_dump() for c in response.charts]
        return [_deep_normalize_chart(ch) for ch in charts]
    return []





def _validate_chart(chart: dict[str, Any]) -> str | None:
    pc = chart.get("pivot_config")
    if not pc or not isinstance(pc, dict):
        return f"图表「{chart.get('title', '未命名')}」缺少 pivot_config"

    values = pc.get("values", [])
    if not isinstance(values, list) or len(values) == 0:
        return f"图表「{chart.get('title', '未命名')}」的 values 为空"

    for i, v in enumerate(values):
        if not isinstance(v, dict):
            return f"图表「{chart.get('title', '未命名')}」values[{i}] 不是有效对象"
        if not v.get("field"):
            return f"图表「{chart.get('title', '未命名')}」values[{i}] 缺少 field"

    axes = pc.get("axes", [])
    if not isinstance(axes, list) or len(axes) == 0:
        return f"图表「{chart.get('title', '未命名')}」的 axes 为空"

    return None


def _validate_charts(charts: list[dict[str, Any]]) -> str | None:
    if not charts:
        return "未生成任何图表配置"
    for chart in charts:
        err = _validate_chart(chart)
        if err:
            return err
    return None


def _save_trace_log(state: ChartState, session_id: str = None) -> str:
    charts = state.get("charts", []) or []
    data_rows = sum(len(ch.get("data", []) or []) for ch in charts)
    sql_snippets = [ch.get("sql", "") for ch in charts]
    return save_trace_log(
        agent_name="chart_agent",
        state=state,
        extra={"chart_count": len(charts), "data_rows": data_rows, "sql": sql_snippets},
        session_id=session_id,
    )


# ---- Pivot 查询 ----

_PIVOT_API_URL: str | None = None


def _get_pivot_api_url() -> str:
    global _PIVOT_API_URL
    if _PIVOT_API_URL is None:
        _PIVOT_API_URL = os.getenv("PIVOT_API_URL", "http://127.0.0.1:8080/api2/pivot/query").rstrip("/")
    return _PIVOT_API_URL


def _pivot_via_http(config: PivotConfig) -> dict:
    import requests
    url = _get_pivot_api_url()
    payload = config.model_dump()
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        detail = resp.json().get("detail", resp.text) if resp.text else resp.reason
        raise RuntimeError(f"Pivot 查询失败: {detail}")
    result = resp.json()
    return {
        "data": result.get("data", []),
        "columns": result.get("columns", []),
        "total": result.get("total", 0),
        "vega_spec": result.get("vega_spec", {}),
        "config": result.get("config"),
        "sql": result.get("sql"),
        "execution_time_ms": result.get("execution_time_ms", 0),
    }


def _categorize_execute_error(error_msg: str) -> str:
    error_lower = error_msg.lower()
    if any(kw in error_lower for kw in ["binder error", "catalog error", "not found", "no column"]):
        return "该字段暂不支持查询，建议尝试其他分析维度"
    if any(kw in error_lower for kw in ["timeout", "timed out"]):
        return "查询超时，请稍后重试"
    return "查询异常，请检查图表配置"


# ============================================================
# Agent Nodes
# ============================================================

def analyze_node(state: ChartState) -> ChartState:
    """图表分析节点：用 Structured Output 调用 LLM 生成配置"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child("analyze", "llm", input={"message": state["user_message"]}) if (tc and parent_span) else None

    try:
        structured_llm = get_structured_llm(AgentOutput)
        system_parts = [_get_chart_system_prompt()]

        if state.get("analyze_retry_count", 0) > 0 and state.get("validation_error"):
            system_parts.append(
                f"注意：上一次生成的配置在校验中未通过，请根据以下反馈修正：\n{state['validation_error']}\n请重新生成符合要求的配置。"
            )

        base_system = "\n\n".join(system_parts)
        messages = [{"role": "system", "content": base_system}]
        history = [h for h in (state.get("conversation_history") or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        response: AgentOutput | None = None
        if structured_llm is not None:
            try:
                response = structured_llm.invoke(messages)
                if sp:
                    sp.messages = list(messages)
                    sp.tokens = {"input": -1, "output": -1}
                    sp.output = response.model_dump()

            except Exception:
                logger.warning("StructuredOutput 调用失败，使用 PydanticOutputParser 兜底")
                response = None

        if response is None:
            parser = PydanticOutputParser(pydantic_object=AgentOutput)
            format_instructions = parser.get_format_instructions()
            fallback_messages = [{"role": "system", "content": f"{base_system}\n\n## 输出格式\n{format_instructions}"}]
            for h in history:
                fallback_messages.append(h)
            fallback_messages.append({"role": "user", "content": state["user_message"]})
            raw_llm = get_llm()
            raw_resp = raw_llm.invoke(fallback_messages)
            raw_content = raw_resp.content.strip()

            try:
                response = parser.parse(raw_content)
            except Exception as parse_err:
                logger.error("PydanticOutputParser 解析失败: %s", parse_err)
                result = try_parse_json(raw_content)
                response = AgentOutput(
                    intent="chart",
                    reply=result.get("reply", str(parse_err)),
                    charts=[],
                    suggestions=result.get("suggestions", []),
                )

            if sp:
                sp.messages = list(fallback_messages)
                sp.tokens = {"input": -1, "output": -1}
                sp.output = response.model_dump()

        state["reply"] = response.reply
        state["suggestions"] = response.suggestions or []
        state["charts"] = _normalize_charts_from_output(response)
        state["ask_questions"] = [q.model_dump() for q in (response.ask_questions or [])]
        state["pending_step"] = "awaiting_questions" if response.ask_questions else None


    except Exception as e:
        logger.error("Agent 分析失败: %s", e, exc_info=True)
        state["error"] = str(e)
        state["reply"] = f"分析时出错：{e}"
        state["charts"] = []
        if sp:
            sp.finish(error=str(e))


    if sp and state.get("error") is None and sp.status == "in_progress":
        sp.finish(output={"reply": state.get("reply"), "chart_count": len(state.get("charts", []))})

    return state


def validate_config_node(state: ChartState) -> ChartState:
    """校验节点：校验 charts 配置合法性，不通过则回流 analyze 重试（最多 1 次）"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp = parent_span.add_child("validate", "chain", input={"chart_count": len(state.get("charts", []))}) if (tc and parent_span) else None

    # trace_log 已废弃，日志由 TraceCollector 管理

    err = _validate_charts(state["charts"])
    if err is None:
        state["validation_error"] = None

        if sp:
            sp.finish(output={"valid": True})
    else:
        retry_count = state.get("analyze_retry_count", 0)
        state["validation_error"] = err

        if retry_count < 1:
            state["analyze_retry_count"] = retry_count + 1
            state["reply"] = f"配置校验未通过（第 1 次重试）：{err}"

            if sp:
                sp.finish(error=f"校验失败（已通知重试）: {err}")
        else:
            state["validation_error"] = None
            state["charts"] = []
            state["error"] = (state.get("error") or "") + f" 配置校验失败（已重试）：{err}"
            if not state.get("reply"):
                state["reply"] = f"配置校验多次失败：{err}，请尝试换个问法。"

            if sp:
                sp.finish(error=f"校验最终失败: {err}")

    return state


def execute_node(state: ChartState) -> ChartState:
    """执行节点：遍历 state.charts 逐个查询数据"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp = parent_span.add_child("execute (Pivot API)", "tool", input={"chart_count": len(state.get("charts", []))}) if (tc and parent_span) else None

    # trace_log 已废弃，日志由 TraceCollector 管理

    charts = state.get("charts", []) or []
    errors: list[str] = []
    api_inputs = []
    api_outputs = []
    for chart in charts:
        pc_dict = chart.get("pivot_config") or chart.get("config")
        ct = chart.get("chart_type", "bar")
        if not pc_dict:
            chart["error"] = "缺少 pivot_config"
            errors.append("缺少 pivot_config")
            continue

        pc_dict["chart_type"] = ct
        try:
            cfg = PivotConfig(**pc_dict)
            api_inputs.append(cfg.model_dump())
            res = _pivot_via_http(cfg)
            chart["data"] = res.get("data", [])
            chart["vega_spec"] = res.get("vega_spec", {})
            chart["sql"] = res.get("sql")
            chart["error"] = None
            api_outputs.append({
                "data_count": len(res.get("data", [])),
                "columns": res.get("columns", []),
                "sql": res.get("sql", ""),
                "execution_time_ms": res.get("execution_time_ms", 0),
            })
        except Exception as e2:
            logger.error("图表执行失败: %s, config=%s", e2, pc_dict)
            friendly_msg = _categorize_execute_error(str(e2))
            chart["error"] = friendly_msg
            chart.setdefault("data", [])
            chart.setdefault("sql", "")
            errors.append(friendly_msg)

    succeed_count = len(charts) - len(errors)
    if sp:
        sp.input = {"api_requests": api_inputs} if api_inputs else {"chart_count": len(charts)}
        sp.finish(
            output={
                "api_responses": api_outputs,
                "charts": succeed_count,
                "error_details": errors,
            } if not errors else {"error_details": errors},
            error="; ".join(errors) if errors else None
        )
    return state


def format_reply_node(state: ChartState) -> ChartState:
    """格式化回复节点：构造最终回复并保存日志"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp = parent_span.add_child("format_reply", "chain", input={"reply_preview": state.get("reply", "")[:100], "suggestions": state.get("suggestions", [])}) if (tc and parent_span) else None

    # trace_log 已废弃，日志由 TraceCollector 管理

    charts = state.get("charts", []) or []
    total_rows = sum(len(ch.get("data", []) or []) for ch in charts)
    chart_errors = [(i, ch) for i, ch in enumerate(charts) if ch.get("error")]
    succeed_count = len(charts) - len(chart_errors)

    summary_parts = []
    if total_rows > 0:
        summary_parts.append(f"共查询到 {total_rows} 条结果。")
    if chart_errors:
        failed_titles = [ch.get("title", f"图表{i+1}") for i, ch in chart_errors]
        summary_parts.append(f"{len(chart_errors)} 个图表查询失败：{'、'.join(failed_titles)}。")
    if succeed_count == 0 and chart_errors:
        summary_parts.append("请尝试换个方式描述分析需求。")

    if summary_parts:
        state["reply"] = (state.get("reply") or "") + "\n\n" + " ".join(summary_parts)

    if sp:
        sp.finish(output={"reply": state.get("reply", "")[:200], "suggestions": state.get("suggestions", [])})

    # Save root span and mark status
    if tc:
        has_error = bool(state.get("error")) or bool(chart_errors)
        if has_error:
            tc.root.finish(error=state.get("error") or "; ".join([ch.get("error", "") for i, ch in chart_errors]))
        else:
            tc.root.finish(output={"reply": state.get("reply", "")[:200], "charts": len(charts)})

    log_path = _save_trace_log(state)
    return state


# ============================================================
# Agent 构建
# ============================================================

def build_chart_agent() -> Any:
    """构建图表分析 Agent

    数据流：
      analyze → validate → execute → format_reply
                 ↑           ↓
                 └──── 重试 ──┘
    """
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(ChartState)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("validate", validate_config_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "validate")

    def route_after_validate(state: ChartState) -> str:
        if state.get("validation_error") and state.get("analyze_retry_count", 0) > 0:
            return "analyze"
        if state.get("validation_error"):
            return "format_reply"
        if state.get("charts"):
            return "execute"
        return "format_reply"

    workflow.add_conditional_edges("validate", route_after_validate, {
        "analyze": "analyze",
        "execute": "execute",
        "format_reply": "format_reply",
    })

    workflow.add_edge("execute", "format_reply")
    workflow.add_edge("format_reply", END)

    return workflow.compile()


async def process_chart(message: str, history: list[dict[str, str]] | None = None, session_id: str | None = None) -> dict[str, Any]:
    """处理图表分析请求"""
    import uuid
    import time

    start = time.time()

    # 创建 TraceCollector
    tc = TraceCollector(
        session_id=session_id or "",
        request_message=message,
        agent_name="chart_agent",
    )

    agent = build_chart_agent()
    thread_id = str(uuid.uuid4())

    state: ChartState = {
        "user_message": message,
        "conversation_history": history or [],
        "reply": "",
        "charts": [],
        "suggestions": [],
        "error": None,
        "analyze_retry_count": 0,
        "validation_error": None,
        "trace_collector": tc,
        "trace_span": tc.root,
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(state, config)

    # 保存完整 trace 到数据库
    tc.save_to_db()

    elapsed = (time.time() - start) * 1000

    return {
        "reply": result.get("reply", ""),
        "charts": result.get("charts", []) or [],
        "is_dashboard": len(result.get("charts", []) or []) > 1,
        "suggestions": result.get("suggestions", []),
        "trace_id": tc.trace_id,
        "execution_time_ms": round(elapsed, 2),
        "ask_questions": result.get("ask_questions", []) or [],
        "pending_step": result.get("pending_step"),
    }
