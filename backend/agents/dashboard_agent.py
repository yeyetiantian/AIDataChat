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


# ============================================================
# 任务名提取
# ============================================================

def _extract_task_from_message(user_msg: str) -> tuple[str | None, str | None]:
    """从用户输入中识别任务，返回 (task_id_str, task_name) 或 (None, None)

    采用多策略级联：
      1. 精确子串匹配 — TASK_NAME 是 user_msg 的子串
      2. 自然语言提取 — 从“为XX创建看板”模式关键词 → 去空格模糊匹配
      3. 任意 token 匹配 — user_msg 中 ≥2 字符的片段逐条匹配
    """
    try:
        from core.chat_db import _get_conn
        conn = _get_conn()

        # 策略1: 精确子串匹配（任务全名在用户输入中）
        cur = conn.execute(
            "SELECT TASK_ID, TASK_NAME FROM ext_tasks WHERE ? LIKE '%' || TASK_NAME || '%' AND (IS_DELETE IS NULL OR IS_DELETE = 0) LIMIT 1",
            (user_msg,),
        )
        row = cur.fetchone()
        if row:
            return str(row[0]), row[1]

        import re

        # 策略2: 从“为XX创建看板”“给XX看板”“关联XX看板”中提取关键词
        patterns = [
            r'[为给关联对](.+?)(?:的)?(?:创建|建立|新建|做一个?|生成)(?:的)?(?:看板|仪表盘|大屏)',
            r'[为给关联对](.+?)(?:的)?(?:看板|仪表盘|大屏)',
            r'(?:给|对|把)(.+?)(?:的)?(?:创建|建立|生成)',
        ]
        for pat in patterns:
            m = re.search(pat, user_msg)
            if m:
                keyword = m.group(1).strip()
                if len(keyword) >= 2:
                    # 去除空格后再匹配（用户打字习惯与数据库可能不同）
                    no_space = keyword.replace(' ', '')
                    cur = conn.execute(
                        "SELECT TASK_ID, TASK_NAME FROM ext_tasks WHERE REPLACE(TASK_NAME, ' ', '') LIKE ? AND (IS_DELETE IS NULL OR IS_DELETE = 0) LIMIT 1",
                        (f"%{no_space}%",),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row[0]), row[1]

        # 策略3: 用 user_msg 中的每个 ≥2 字符 token 去模糊匹配
        tokens = [t for t in re.split(r'[\s,，、]+', user_msg) if len(t) >= 2]
        for token in tokens:
            no_space_token = token.replace(' ', '')
            cur = conn.execute(
                "SELECT TASK_ID, TASK_NAME FROM ext_tasks WHERE REPLACE(TASK_NAME, ' ', '') LIKE ? AND (IS_DELETE IS NULL OR IS_DELETE = 0) LIMIT 1",
                (f"%{no_space_token}%",),
            )
            row = cur.fetchone()
            if row:
                return str(row[0]), row[1]
    except Exception as exc:
        logger.warning("提取任务名称失败: %s", exc)
    return None, None

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
2. 如果用户消息明确说明了要多少个图表、每个图表展示什么，或是对已有看板进行修改/补充 → 提取为 chart_infos 列表，is_complete=true
3. 如果用户只说了"帮我创建一个看板"或非常模糊的需求，且不是对已有看板的修改 → is_complete=false，列出 missing_info

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


def _init_dashboard_questionnaire(state: dict, user_msg: str):
    """初始化看板问卷，并尝试从用户输入中预填任务信息"""
    state["ask_questions"] = _build_dashboard_questionnaire()
    preset_id, preset_name = _extract_task_from_message(user_msg)
    if preset_id and preset_name:
        for q in state["ask_questions"]:
            if q["id"] == "task_id":
                q["preset_value"] = preset_id
                q["preset_label"] = preset_name
                break
        state["reply"] = f"好的，我来帮您创建一个看板！已识别任务「{preset_name}」，请确认以下信息："
    else:
        state["reply"] = "好的，我来帮您创建一个看板！请先告诉我一些基本信息："


# ============================================================
# Agent Nodes
# ============================================================

def check_completeness_node(state: DashboardState) -> DashboardState:
    """Step 1: 分析信息是否完善，仅非常模糊的创建需求才返回问卷"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child("check_completeness", "llm", input={"message": state["user_message"]}) if (tc and parent_span) else None

    _draft = state.get("dashboard_draft")
    _user_msg = state["user_message"]

    # ---- 快速路径 1: 有结构化的看板草案 → 直接提取 chart_infos ----
    if _draft:
        chart_infos = _extract_chart_infos_from_draft(_draft)
        if chart_infos:
            logger.info("check_completeness: 从草案提取 %d 个图表描述", len(chart_infos))
            state["chart_infos"] = chart_infos
            state["reply"] = "好的，已获取看板需求，正在生成图表配置..."
            if sp:
                sp.finish(output={"complete": True, "chart_count": len(chart_infos), "source": "draft"})
            return state

    # ---- 快速路径 2: 仅有模糊的创建意图时才需要问卷 ----
    # 以下情况视为"具体需求"，不需要问卷:
    #   - 包含修改/调整词汇
    #   - 包含具体图表类型/维度关键词
    #   - 包含分析维度指标

    _modification_kws = ["改成", "改为", "修改", "调整", "换为", "换成", "加一个", "新增", "添加", "补充"]
    _specific_chart_kws = [
        "柱状", "折线", "饼图", "雷达", "面积", "散点", "趋势", "分布", "对比", "排名",
        "各", "按", "次数", "数量", "占比", "排行", "信号", "报警",
    ]

    has_modification = any(kw in _user_msg for kw in _modification_kws)
    has_specific_chart = any(kw in _user_msg for kw in _specific_chart_kws)
    has_chart_ref = any(kw in _user_msg for kw in ["图表", "图"])  # 提到图表

    # 判断是否为纯粹的模糊创建看板请求
    is_vague_dashboard_creation = (
        not has_modification
        and not has_specific_chart
        and not has_chart_ref
        and any(kw in _user_msg for kw in ["创建看板", "新建看板", "做一个看板", "生成看板", "数据大屏", "新建一个看板"])
    ) or (
        not has_modification
        and not has_specific_chart
        and not has_chart_ref
        and "看板" in _user_msg
        and len(_user_msg) < 15  # 极短的看板请求
    )

    if is_vague_dashboard_creation:
        logger.info("check_completeness: 模糊创建看板请求，返回问卷")
        _init_dashboard_questionnaire(state, _user_msg)
        state["pending_step"] = "awaiting_questions"
        state["chart_infos"] = []
        if sp:
            sp.finish(output={"complete": False, "reason": "模糊看板创建需求"})
        return state

    # ---- 非模糊需求：用 LLM 提取结构化的图表信息 -----
    # 包括：具体修改、补充图表、有特定维度的分析等
    try:
        system_prompt = _COMPLETENESS_PROMPT
        messages = [{"role": "system", "content": system_prompt}]
        history = [h for h in (state.get("conversation_history") or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": _user_msg})

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
            fallback_messages.append({"role": "user", "content": _user_msg})
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

        # 只要 LLM 认为完善或有 chart_infos 就继续
        if completeness.is_complete and completeness.chart_infos:
            logger.info("check_completeness: LLM 分析认为完善，提取 %d 个图表", len(completeness.chart_infos))
            state["chart_infos"] = completeness.chart_infos
            state["reply"] = completeness.reply or "好的，已解析您的需求，正在生成图表配置..."
        else:
            # LLM 认为不完善→ 检查是否有具体关键词（兜底）
            if has_specific_chart or has_chart_ref or has_modification:
                logger.info("check_completeness: 虽有具体关键词但 LLM 判不完善，直接使用用户消息作为 chart_info")
                state["chart_infos"] = [state["user_message"]]
                state["reply"] = "好的，正在生成图表配置..."
            else:
                logger.info("check_completeness: 信息不完善：%s", completeness.reason)
                _init_dashboard_questionnaire(state, _user_msg)
                state["pending_step"] = "awaiting_questions"
                state["chart_infos"] = []

    except Exception as e:
        logger.error("check_completeness 失败: %s", e, exc_info=True)
        # 降级：用关键词检查
        if has_specific_chart or has_chart_ref or has_modification:
            state["chart_infos"] = [state["user_message"]]
            state["reply"] = "好的，正在生成图表配置..."
        else:
            _init_dashboard_questionnaire(state, _user_msg)
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
    step_callback: Any | None = None,
) -> dict[str, Any]:
    """处理看板生成请求

    Args:
        step_callback: 可选的回调，用于流式推送子步骤 async (node, status, label, detail) -> None
    """
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

    if step_callback:
        result = None
        _dash_node_labels = {
            "check_completeness": ("dashboard.check", "检查信息完整度", "信息完整"),
            "generate_charts": ("dashboard.generate", "生成图表配置", "配置生成完成"),
            "execute": ("dashboard.execute", "执行批量查询", "数据查询完成"),
            "format_reply": ("dashboard.format", "整理看板结果", "结果已整理"),
        }

        def _dash_next(node_name: str, full: dict) -> str | None:
            if node_name == "check_completeness":
                if full.get("pending_step") == "awaiting_questions":
                    return "format_reply"
                if full.get("chart_infos"):
                    return "generate_charts"
                return "format_reply"
            elif node_name == "generate_charts":
                return "execute"
            elif node_name == "execute":
                return "format_reply"
            return None

        def _dash_detail(node_name: str, full: dict) -> str:
            if node_name == "check_completeness":
                if full.get("pending_step") == "awaiting_questions":
                    return "信息不完善，需要向用户提问"
                infos = full.get("chart_infos") or []
                if infos:
                    return f"识别到 {len(infos)} 个图表需求"
                reply = full.get("reply") or ""
                return reply[:200] if reply else "信息检查完成"
            elif node_name == "generate_charts":
                charts = full.get("charts") or []
                reply = full.get("reply") or ""
                if charts:
                    titles = [ch.get("title", "") or "" for ch in charts[:3]]
                    return f"生成 {len(charts)} 个配置: {', '.join(filter(None, titles))}"[:300]
                return reply[:200] if reply else "配置生成完成"
            elif node_name == "execute":
                charts = full.get("charts") or []
                total = sum(len(ch.get("data", []) or []) for ch in charts)
                errors = [ch.get("error") for ch in charts if ch.get("error")]
                parts = []
                if total:
                    parts.append(f"共 {total} 条数据")
                if errors:
                    parts.append(f"失败 {len(errors)} 个")
                return "、".join(parts) if parts else "批量查询完成"
            elif node_name == "format_reply":
                reply = full.get("reply") or ""
                return reply[:300] if reply else "结果已整理"
            return ""

        full_state = dict(state)
        entry = _dash_node_labels["check_completeness"]
        await step_callback(entry[0], "running", entry[1], "")

        async for update in agent.astream(state, config, stream_mode="updates"):
            for node_name, partial in update.items():
                full_state.update(partial)
                result = full_state
                if node_name in _dash_node_labels:
                    labels = _dash_node_labels[node_name]
                    detail = _dash_detail(node_name, full_state)
                    if full_state.get("error"):
                        await step_callback(labels[0], "error", labels[2], f"出错: {full_state['error']}")
                    else:
                        await step_callback(labels[0], "done", labels[2], detail)

                    next_node = _dash_next(node_name, full_state)
                    if next_node and next_node in _dash_node_labels:
                        next_labels = _dash_node_labels[next_node]
                        await step_callback(next_labels[0], "running", next_labels[1], "")

        if result is None:
            result = full_state
    else:
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
