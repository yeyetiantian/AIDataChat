"""看板分析子 Agent — 多图表生成 + 交互式问卷

数据流：
  check_completeness（LLM 分析信息是否完善）
    → 不完善 → 看板问卷 / 询问用户 → format_reply
    → 完善 → 提取图表信息列表 → generate_charts（生成配置 + 调用 Pivot API）→ format_reply
"""

from __future__ import annotations

import logging
import os
from typing import Any, TypedDict

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from agents.llm_utils import (
    get_llm,
    get_structured_llm,
    call_structured,
    try_parse_json,
    save_trace_log,
    TraceCollector,
    SpanNode,
)
from agents.chart_agent import (
    ChartItem,
    AgentOutput,
    _get_chart_system_prompt,
    _deep_normalize_chart,
    _normalize_charts_from_output,
    pivot_via_http,
    _categorize_execute_error,
)
from services.query_preprocessor import ParsedChartRequest, preprocess_chart_query
from models import PivotConfig

logger = logging.getLogger("dashboard_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# 结构化输出模型
# ============================================================

class CompletenessOutput(BaseModel):
    """信息完善度分析结果"""
    is_complete: bool = Field(description="当前信息是否足够生成看板")
    reason: str = Field("", description="分析理由")
    chart_infos: list[str] = Field(default_factory=list, description="各图表的描述文本列表，每项对应一个图表的需求")
    missing_info: list[str] = Field(default_factory=list, description="缺失的关键信息项")

    reply: str = Field("", description="回复用户的话")


# ============================================================
# 看板问卷构建
# ============================================================

def _build_dashboard_questionnaire() -> list[dict]:
    """构建看板需求问卷（前端处理图表槽、规则/信号拖拽）"""
    return [
        {"id": "chart_count", "question": "需要展示多少个图表？", "type": "select", "options": [
            {"label": "1个", "value": "1"}, {"label": "2个", "value": "2"}, {"label": "3个", "value": "3", "recommended": True},
            {"label": "4个", "value": "4"}, {"label": "5个", "value": "5"}, {"label": "6个", "value": "6"}
        ], "placeholder": "", "required": True},
        {"id": "task_id", "question": "关联哪个任务？", "type": "select", "options_api": "/api/functions/tasks", "options": [], "placeholder": "", "required": True},
        {"id": "rule_list", "question": "可用规则", "type": "rule_list", "options_api": "/api/functions/rules", "options": [], "placeholder": "", "required": False, "depends_on": "task_id"},
        {"id": "signal_list", "question": "可用信号", "type": "signal_list", "options_api": "/api/functions/signals", "options": [], "placeholder": "", "required": False, "depends_on": ["task_id", "rule_list"]},
        {"id": "date", "question": "需要什么时间范围？", "type": "date-range", "placeholder": "", "required": True},
        {"id": "chart_slots", "question": "图表配置", "type": "chart_slots", "options": [], "placeholder": "", "required": True, "depends_on": "chart_count"},
    ]


# ============================================================
# 完善度检查 Prompt
# ============================================================

_COMPLETENESS_PROMPT = """你是看板需求分析助手。分析用户输入的信息是否足够生成一个多图表看板。

判断标准：
1. 如果用户已通过问卷提交了结构化的看板草案（包含任务ID、图表数量、各图表描述）→ is_complete=true
2. 如果用户消息明确说明了要多少个图表、每个图表展示什么 → 提取为 chart_infos 列表，is_complete=true
3. 如果用户只说了"帮我创建一个看板"或非常模糊的需求 → is_complete=false，列出 missing_info

chart_infos 格式：每项是一个图表的需求描述文本，如"生成饼图，分析规则产生报警的数量占比"。
如果信息不完善，missing_info 列出缺失的关键项。"""


# ---- Agent State ----
class DashboardState(TypedDict):
    """看板分析状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    reply: str
    charts: list[dict[str, Any]]
    suggestions: list[str]
    error: str | None

    trace_collector: TraceCollector | None
    trace_span: SpanNode | None

    # 看板专用字段
    ask_questions: list[dict[str, Any]]
    pending_step: str | None  # "awaiting_questions" / None
    dashboard_draft: dict[str, Any] | None

    # 图表信息列表（由 check_completeness 提取）
    chart_infos: list[str]


# ---- 工具函数 ----

def _save_trace_log_fn(state: DashboardState, session_id: str = None) -> str:
    charts = state.get("charts", []) or []
    data_rows = sum(len(ch.get("data", []) or []) for ch in charts)
    sql_snippets = [ch.get("sql", "") for ch in charts]
    return save_trace_log(
        agent_name="dashboard_agent",
        state=state,
        extra={"chart_count": len(charts), "data_rows": data_rows, "sql": sql_snippets},
        session_id=session_id,
    )


def _extract_chart_infos_from_draft(draft: dict) -> list[str]:
    """从看板草案中提取图表描述列表"""
    infos: list[str] = []
    slots = draft.get('chart_slots', [])
    for sl in slots:
        if isinstance(sl, dict):
            raw = sl.get('description') or sl.get('dimension') or ''
        else:
            raw = str(sl) if sl else ''
        if not isinstance(raw, str):
            raw = str(raw)
        text = raw.strip()
        if text:
            infos.append(text)
    return infos


# ============================================================
# Agent Nodes
# ============================================================

def check_completeness_node(state: DashboardState) -> DashboardState:
    """Step 1: 用 LLM 分析信息是否完善，不完善则返回问卷"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child("check_completeness", "llm", input={"message": state["user_message"]}) if (tc and parent_span) else None

    _draft = state.get("dashboard_draft")

    # 有结构化的看板草案 → 直接提取 chart_infos
    if _draft:
        chart_infos = _extract_chart_infos_from_draft(_draft)
        if chart_infos:
            logger.info("check_completeness: 从草案提取 %d 个图表描述", len(chart_infos))
            state["chart_infos"] = chart_infos
            state["reply"] = "好的，已获取看板需求，正在生成图表配置..."
            if sp:
                sp.finish(output={"complete": True, "chart_count": len(chart_infos), "source": "draft"})
            return state

    # 无 draft → 用 LLM 分析用户消息是否足够
    try:
        system_prompt = _COMPLETENESS_PROMPT
        messages = [{"role": "system", "content": system_prompt}]
        history = [h for h in (state.get("conversation_history") or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        if sp:
            sp.messages = list(messages)

        completeness = call_structured(CompletenessOutput, messages)

        if completeness is None:
            # 回退：PydanticOutputParser
            parser = PydanticOutputParser(pydantic_object=CompletenessOutput)
            format_instructions = parser.get_format_instructions()
            fallback_messages = [{
                "role": "system",
                "content": f"{system_prompt}\n\n## 输出格式\n{format_instructions}",
            }]
            for h in history:
                fallback_messages.append(h)
            fallback_messages.append({"role": "user", "content": state["user_message"]})
            raw = get_llm().invoke(fallback_messages)
            raw_content = raw.content.strip() if hasattr(raw, 'content') else str(raw)
            try:
                completeness = parser.parse(raw_content)
            except Exception:
                parsed = try_parse_json(raw_content) or {}
                completeness = CompletenessOutput(
                    is_complete=bool(parsed.get("chart_infos")),
                    reason=parsed.get("reason", ""),
                    chart_infos=parsed.get("chart_infos", []),
                    missing_info=parsed.get("missing_info", []),
                )

        if sp:
            sp.output = completeness.model_dump()
            sp.finish(output=completeness.model_dump())

        if completeness.is_complete and completeness.chart_infos:
            logger.info("check_completeness: LLM 分析认为完善，提取 %d 个图表", len(completeness.chart_infos))
            state["chart_infos"] = completeness.chart_infos
            state["reply"] = completeness.reply or "好的，已解析您的需求，正在生成图表配置..."
        else:
            logger.info("check_completeness: 信息不完善：%s", completeness.reason)
            state["reply"] = completeness.reply or "好的，我来帮您创建一个看板！请先告诉我一些基本信息："
            state["ask_questions"] = _build_dashboard_questionnaire()
            state["pending_step"] = "awaiting_questions"
            state["chart_infos"] = []

    except Exception as e:
        logger.error("check_completeness 失败: %s", e, exc_info=True)
        # 降级：用关键词检查
        _has_specific = any(kw in state["user_message"] for kw in [
            "图表", "图", "柱状", "折线", "饼图", "雷达", "面积", "散点",
            "次数", "数量", "占比", "排行", "趋势", "对比",
        ])
        if _has_specific:
            state["chart_infos"] = [state["user_message"]]
            state["reply"] = "好的，正在生成图表配置..."
        else:
            state["reply"] = "好的，我来帮您创建一个看板！请先告诉我一些基本信息："
            state["ask_questions"] = _build_dashboard_questionnaire()
            state["pending_step"] = "awaiting_questions"
            state["chart_infos"] = []
        if sp:
            sp.finish(error=str(e))

    return state


def generate_charts_node(state: DashboardState) -> DashboardState:
    """Step 2: 根据 chart_infos 列表生成多个图表的 PivotConfig"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child("generate_charts", "llm", input={
        "chart_count": len(state.get("chart_infos", [])),
    }) if (tc and parent_span) else None

    chart_infos = state.get("chart_infos", [])
    if not chart_infos:
        state["error"] = "缺少图表信息列表，无法生成配置"
        if sp:
            sp.finish(error="chart_infos 为空")
        return state

    try:
        system_parts = [_get_chart_system_prompt()]
        parsedList: list[ParsedChartRequest] = []

        for info in chart_infos:
            parsed = preprocess_chart_query(info)
            parsed_text = parsed.to_prompt_section()
            parsedList.append(parsed)
            if parsed_text:
                system_parts.append(parsed_text)

        base_system = "\n\n".join(system_parts)
        messages = [{"role": "system", "content": base_system}]
        history = [h for h in (state.get("conversation_history") or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        if sp:
            sp.messages = list(messages)

        response = call_structured(AgentOutput, messages)
        llm_raw_content = None

        if response is None:
            parser = PydanticOutputParser(pydantic_object=AgentOutput)
            format_instructions = parser.get_format_instructions()
            fallback_messages = [{"role": "system", "content": f"{base_system}\n\n## 输出格式\n{format_instructions}"}]
            for h in history:
                fallback_messages.append(h)
            fallback_messages.append({"role": "user", "content": state["user_message"]})
            raw_llm = get_llm()
            raw_resp2 = raw_llm.invoke(fallback_messages)
            raw_content = raw_resp2.content.strip()
            llm_raw_content = raw_content
            if sp:
                sp.messages = list(fallback_messages)
                sp.output = {"llm_raw_content": raw_content}
            try:
                response = parser.parse(raw_content)
            except Exception as parse_err:
                result = try_parse_json(raw_content)
                response = AgentOutput(
                    intent="dashboard",
                    reply=result.get("reply", str(parse_err)),
                    charts=[],
                    suggestions=result.get("suggestions", []),
                )

        if sp:
            existing = sp.output or {}
            sp.output = {
                **existing,
                "structured": response.model_dump(),
                "llm_raw_content": existing.get("llm_raw_content") or llm_raw_content,
            }

        state["reply"] = response.reply
        state["suggestions"] = response.suggestions or []
        state["charts"] = _normalize_charts_from_output(response, parsedList)

    except Exception as e:
        logger.error("generate_charts 失败: %s", e, exc_info=True)
        state["error"] = str(e)
        state["reply"] = f"生成图表配置时出错：{e}"
        state["charts"] = []
        if sp:
            sp.finish(error=str(e))

    if sp and state.get("error") is None and sp.status == "in_progress":
        prev_out = sp.output or {}
        sp.finish(output={
            "reply": state.get("reply"),
            "chart_count": len(state.get("charts", [])),
            "structured": prev_out.get("structured"),
            "llm_raw_content": prev_out.get("llm_raw_content"),
        })

    return state


def execute_node(state: DashboardState) -> DashboardState:
    """Step 3: 调用 Pivot API 查询数据（失败不重试）"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp = parent_span.add_child("execute (Pivot API)", "tool", input={"chart_count": len(state.get("charts", []))}) if (tc and parent_span) else None

    charts = state.get("charts", []) or []
    errors: list[str] = []
    api_inputs = []
    api_outputs = []
    for chart in charts:
        pc_dict = chart.get("pivot_config") or chart.get("config")
        if not pc_dict:
            chart["error"] = "缺少 pivot_config"
            errors.append("缺少 pivot_config")
            continue
        try:
            cfg = PivotConfig(**pc_dict)
            api_inputs.append(cfg.model_dump())
            res = pivot_via_http(cfg)
            chart["data"] = res.get("data", [])
            chart["chart_type"] = pc_dict.get("chart_type", "bar")
            chart["vega_spec"] = res.get("vega_spec", {})
            chart["sql"] = res.get("sql")
            chart["error"] = None
            api_outputs.append({
                "data": res.get("data", []),
                "columns": res.get("columns", []),
                "total": res.get("total", 0),
                "vega_spec": res.get("vega_spec", {}),
                "config": res.get("config"),
                "sql": res.get("sql", ""),
                "execution_time_ms": res.get("execution_time_ms", 0),
            })
        except Exception as e2:
            logger.error("图表执行失败: %s", e2)
            friendly_msg = _categorize_execute_error(str(e2))
            chart["error"] = friendly_msg
            chart.setdefault("data", [])
            chart.setdefault("sql", "")
            errors.append(friendly_msg)

    succeed_count = len(charts) - len(errors)
    state["execution_error"] = "；".join(errors) if errors else None
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


def format_reply_node(state: DashboardState) -> DashboardState:
    """Step 4: 构造最终回复并保存日志"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp = parent_span.add_child("format_reply", "chain", input={"reply": state.get("reply", ""), "suggestions": state.get("suggestions", [])}) if (tc and parent_span) else None

    # 如果信息不完善进入了问卷模式，直接返回
    if state.get("pending_step") == "awaiting_questions":
        if sp:
            sp.finish(output={"mode": "questionnaire", "ask_questions": len(state.get("ask_questions", []))})
        _save_trace_log_fn(state)
        return state

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
        sp.finish(output={"reply": state.get("reply", ""), "suggestions": state.get("suggestions", [])})

    _save_trace_log_fn(state)
    return state


# ============================================================
# Agent 构建
# ============================================================

def build_dashboard_agent() -> Any:
    """构建看板分析 Agent"""
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(DashboardState)
    workflow.add_node("check_completeness", check_completeness_node)
    workflow.add_node("generate_charts", generate_charts_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("check_completeness")
    workflow.add_edge("generate_charts", "execute")
    workflow.add_edge("execute", "format_reply")
    workflow.add_edge("format_reply", END)

    def route_after_completeness(state: DashboardState) -> str:
        if state.get("pending_step") == "awaiting_questions":
            return "format_reply"
        if state.get("chart_infos"):
            return "generate_charts"
        return "format_reply"

    workflow.add_conditional_edges("check_completeness", route_after_completeness, {
        "generate_charts": "generate_charts",
        "format_reply": "format_reply",
    })

    return workflow.compile()


async def process_dashboard(
    message: str,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    intent: str = "dashboard",
    dashboard_draft: dict[str, Any] | None = None,
    trace_collector: TraceCollector | None = None,
    parent_span: SpanNode | None = None,
) -> dict[str, Any]:
    """处理看板生成请求"""
    import uuid
    import time

    start = time.time()

    if trace_collector and parent_span:
        tc = trace_collector
        agent_span = parent_span.add_child(
            "dashboard_agent", "agent",
            input={"message": message, "intent": intent, "has_draft": dashboard_draft is not None, "session_id": session_id},
        )
    else:
        tc = TraceCollector(
            session_id=session_id or "",
            request_message=message,
            agent_name="dashboard_agent",
        )
        agent_span = tc.root

    agent = build_dashboard_agent()
    thread_id = str(uuid.uuid4())

    state: DashboardState = {
        "user_message": message,
        "conversation_history": history or [],
        "reply": "",
        "charts": [],
        "suggestions": [],
        "error": None,
        "trace_collector": tc,
        "trace_span": agent_span,
        "ask_questions": [],
        "pending_step": None,
        "dashboard_draft": dashboard_draft,
        "chart_infos": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(state, config)

    has_error = bool(result.get("error")) or bool(
        [ch for ch in (result.get("charts") or []) if ch.get("error")]
    )
    if has_error:
        agent_span.finish(error=result.get("error") or "部分图表执行失败")
    else:
        agent_span.finish(output={
            "reply": result.get("reply", ""),
            "charts": len(result.get("charts") or []),
        })

    if trace_collector is None:
        tc.save_to_db()

    elapsed = (time.time() - start) * 1000

    return {
        "reply": result.get("reply", ""),
        "charts": result.get("charts", []) or [],
        "is_dashboard": True,
        "suggestions": result.get("suggestions", []),
        "trace_id": tc.trace_id,
        "execution_time_ms": round(elapsed, 2),
        "ask_questions": result.get("ask_questions", []) or [],
        "pending_step": result.get("pending_step"),
    }
