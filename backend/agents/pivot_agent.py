"""LangGraph NL2SQL Agent

将用户自然语言转换为 PivotConfig + DuckDB SQL。
使用 LangChain Structured Output 强制 JSON 结构化输出。
保留完整链路日志（每个节点的原始输入/输出 + SQL）。

支持一次生成多种图表：如"各车型和各规则的报警次数"→2个图表。
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from core.field_registry import get_schema_for_agent
from core.pivot_sql_builder import execute_pivot
from models import PivotConfig

logger = logging.getLogger("pivot_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Structured Output 模型
# ============================================================

class ChartItem(BaseModel):
    """单个图表配置"""
    title: str = Field("", description="图表标题说明")
    pivot_config: PivotConfig = Field(..., description="透视表配置")
    chart_type: Literal["bar", "line", "area", "point", "pie", "radar"] = Field(
        "bar", description="图表类型"
    )


class AgentOutput(BaseModel):
    """LLM 结构化输出：聊天或图表（支持多图表）"""
    intent: Literal["chat", "chart"] = Field(description="chat=普通聊天, chart=图表分析")
    reply: str = Field(description="回复内容")
    # 单图表（兼容）
    pivot_config: Optional[PivotConfig] = Field(None, description="图表配置（单图表时使用）")
    chart_type: Optional[Literal["bar", "line", "area", "point", "pie", "radar"]] = Field(
        None, description="图表类型（单图表时使用）"
    )
    # 多图表：用户要求"同时看多个维度"时使用
    charts: list[ChartItem] = Field(default_factory=list, description="多图表（一次生成多个图表时使用）")
    suggestions: list[str] = Field(default_factory=list, description="建议用户追问的 3 个问题")


# ============================================================
# 全局缓存（单例）
# ============================================================

_llm: Optional[ChatOpenAI] = None
_structured_llm: Any = None
_schema_cache: Optional[str] = None
_base_system_prompt: Optional[str] = None


def _get_llm() -> ChatOpenAI:
    """全局单例 ChatOpenAI"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
    return _llm


def _get_structured_llm() -> Any:
    """全局单例 Structured Output LLM（绑定 AgentOutput 模型）

    DeepSeek API 暂不支持 response_format / function_calling 强制结构化，
    保留此方法做尝试，失败则回退到手动解析。
    """
    global _structured_llm
    if _structured_llm is None:
        try:
            _structured_llm = _get_llm().with_structured_output(AgentOutput, method="function_calling")
        except Exception:
            logger.warning("StructuredOutput 初始化失败（DeepSeek API 兼容限制），将使用手动 JSON 解析")
            _structured_llm = None
    return _structured_llm


def _get_schema_text() -> str:
    """全局缓存的 Schema 文本"""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = get_schema_for_agent(top_signals=60)
    return _schema_cache


def _get_base_system_prompt() -> str:
    """只构建一次的 System Prompt 基础内容（不含对话上下文）"""
    global _base_system_prompt
    if _base_system_prompt is not None:
        return _base_system_prompt

    schema = _get_schema_text()
    _base_system_prompt = f"""你是数据分析助手，支持三种模式：普通聊天、单图表分析、多图表分析。

## 数据库
你的数据来源是明细宽表 **WIDE_DETAIL**，包含以下字段：

{schema}

## 行为规则

### 1. 普通聊天模式
用户只是打招呼、问简单问题，直接回复即可。
suggestions 字段必须为空列表（无需生成追问）。

### 2. 单图表模式
用户想要查看一个维度的统计，生成一个图表。
使用 pivot_config + chart_type 字段。

### 3. 多图表模式（一次生成多个图表）
当用户同时要求查看多个维度的数据时（如"各车型和各规则的报警次数"），
使用 charts 数组，每个元素是一个完整的图表配置。

多图表示例：
{{{{"intent": "chart", "reply": "我生成了两个图表：", "charts": [
  {{{{ "title": "各车型报警次数", "pivot_config": {{{{ "axes": [{{{{"field": "vehicle_type", "alias": "车型"}}}}], "values": [{{{{"id": "val_1", "field": "alarm_time", "aggregation": "count", "alias": "报警次数"}}}}] }}}}, "chart_type": "bar" }}}},
  {{{{ "title": "各规则类型报警次数", "pivot_config": {{{{ "axes": [{{{{"field": "rule_type", "alias": "规则类型"}}}}], "values": [{{{{"id": "val_1", "field": "alarm_time", "aggregation": "count", "alias": "报警次数"}}}}] }}}}, "chart_type": "bar" }}}}
]}}}}

**支持用户自定义筛选和二次追问修正：**
- "只看SUV的" → 在 filters 中添加筛选条件
- "改成折线图" → 修改 chart_type
- "按天统计" → 在 axes 的 field 上添加 group (day)
- "再加个图例按规则名称" → 在 legend 中添加字段

**对话历史中的前一次 pivot_config 可作为基础进行迭代修改。**
检查 conversation_history 中的上一次 assistant 回复，
提取其中的 pivot_config 做增量修改，而不是每次都从头生成。

### 图表字段说明
- axes: 横轴/行维度字段（GROUP BY）
- legend: 图例字段（PIVOT ON，用于多系列对比）
- values: 聚合值字段，aggregation: count/sum/avg/min/max/count_distinct
- filters: WHERE 筛选条件，op: =/!=/>/>=/</<=/between/in/like
- chart_type: bar/line/area/point/pie/radar（时间序列→line，类别对比→bar，占比→pie）
- group: 时间粒度 year/quarter/month/week/day/hour（仅时间字段）

### SQL 要求
- 固定字段（person/vehicle_type/vehicle/task/rule_name/rule_type/alarm_time/duration_sec）可直接引用
- 对信号列（如 IBSBatSOC、PrplsnSysAtv）做数值聚合时，使用 TRY_CAST("信号名" AS DOUBLE)"""
    return _base_system_prompt


# ---- Agent State ----
class AgentState(TypedDict):
    """Agent 状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    intent: Optional[str]
    pivot_config: Optional[dict[str, Any]]
    chart_type: Optional[str]
    charts: list[dict[str, Any]]          # 多图表 [{pivot_config, chart_type, data, vega_spec, sql, title}]
    suggestions: list[str]
    sql: Optional[str]
    data: Optional[list[dict[str, Any]]]
    vega_spec: Optional[dict[str, Any]]
    reply: str
    error: Optional[str]
    trace_log: list[dict[str, Any]]


def _snapshot(state: AgentState) -> dict:
    """对 state 做安全快照（去掉超大字段，用于日志）"""
    s = dict(state)
    s["trace_log"] = f"<{len(state.get('trace_log', []))} entries>"
    if s.get("charts"):
        s["charts"] = f"<{len(s['charts'])} charts>"
    if s.get("data"):
        s["data"] = f"<{len(s['data'])} rows>"
    if s.get("conversation_history"):
        s["conversation_history"] = f"<{len(s['conversation_history'])} msgs>"
    return s


def _save_trace_log(state: AgentState, session_id: str = None) -> str:
    """保存 Agent 链路日志到文件"""
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    log_entry = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "user_message": state.get("user_message", ""),
        "intent": state.get("intent"),
        "pivot_config": state.get("pivot_config"),
        "sql": state.get("sql"),
        "data_rows": len(state.get("data", []) or []),
        "chart_count": len(state.get("charts", [])),
        "reply": state.get("reply"),
        "suggestions": state.get("suggestions"),
        "error": state.get("error"),
        "trace": state.get("trace_log", []),
    }

    log_path = os.path.join(LOG_DIR, f"agent_{session_id}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
    return log_path


# ---- 数据标准化 ----

def _normalize_pivot(raw: Any) -> dict | None:
    """确保 pivot_config 的 values 每条都有 id，LLM 可能遗漏"""
    if not isinstance(raw, dict):
        return None
    values = raw.get("values", [])
    if isinstance(values, list):
        for i, v in enumerate(values):
            if isinstance(v, dict) and not v.get("id"):
                v["id"] = f"val_{i + 1}"
    return raw


# ---- Agent Nodes ----

def analyze_node(state: AgentState) -> AgentState:
    """NL2SQL 分析节点：用 Structured Output 调用 LLM 生成配置"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "analyze_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    try:
        # 尝试 Structured Output（DeepSeek 可能不支持，静默回退）
        structured_llm = _get_structured_llm()

        messages = [
            {"role": "system", "content": _get_base_system_prompt()},
        ]
        for h in (state.get("conversation_history") or []):
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        response: AgentOutput | None = None
        if structured_llm is not None:
            try:
                response = structured_llm.invoke(messages)
                trace.append({
                    "step": "llm_structured_output",
                    "timestamp": datetime.now().isoformat(),
                    "raw_output": response.model_dump_json()[:1000],
                })
            except Exception:
                logger.warning("StructuredOutput 调用失败，回退到手动解析")
                response = None

        if response is None:
            # 回退：手动 JSON 解析
            raw_llm = _get_llm()
            raw_resp = raw_llm.invoke(messages)
            content = raw_resp.content.strip()

            trace.append({
                "step": "llm_raw_response",
                "timestamp": datetime.now().isoformat(),
                "raw_output": content[:1000],
            })

            import re
            result = None
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if json_match:
                try:
                    result = json.loads(json_match.group(1).strip())
                except json.JSONDecodeError:
                    pass
            if result is None:
                try:
                    result = json.loads(content)
                except json.JSONDecodeError:
                    raise ValueError(f"LLM 返回无法解析为 JSON: {content[:200]}")

            # 手动构建 AgentOutput
            # 提取 charts（多图表）或 pivot_config（单图表）
            raw_charts = result.get("charts")
            if isinstance(raw_charts, list) and len(raw_charts) > 0:
                # 多图表模式
                response = AgentOutput(
                    intent=result.get("intent", "chart"),
                    reply=result.get("reply", ""),
                    charts=raw_charts,
                    suggestions=result.get("suggestions", []),
                )
            else:
                response = AgentOutput(
                    intent=result.get("intent", "chart"),
                    reply=result.get("reply", ""),
                    pivot_config=_normalize_pivot(result.get("pivot_config")),
                    chart_type=result.get("chart_type"),
                    suggestions=result.get("suggestions", []),
                )

        if response.intent == "chat":
            state["intent"] = "chat"
            state["reply"] = response.reply
            state["suggestions"] = []
            state["pivot_config"] = None
            state["chart_type"] = "bar"
            state["charts"] = []
            state["error"] = None
            trace.append({"step": "analyze_complete", "intent": "chat"})
        else:
            state["intent"] = "chart"
            state["suggestions"] = response.suggestions or []
            state["reply"] = response.reply
            state["error"] = None
            if response.charts:
                state["charts"] = [c.model_dump() for c in response.charts]
                state["pivot_config"] = None
                state["chart_type"] = "bar"
                trace.append({"step": "analyze_complete", "intent": "chart", "chart_count": len(response.charts)})
            else:
                pc = response.pivot_config
                state["pivot_config"] = pc.model_dump() if pc else None
                state["chart_type"] = response.chart_type or "bar"
                state["charts"] = []
                trace.append({"step": "analyze_complete", "intent": "chart", "has_config": pc is not None})

    except Exception as e:
        logger.error("Agent 分析失败: %s", e, exc_info=True)
        state["error"] = str(e)
        state["reply"] = f"分析时出错：{e}"
        state["chart_type"] = "bar"
        trace.append({"step": "analyze_error", "error": str(e)})

    trace.append({
        "step": "analyze_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


def execute_node(state: AgentState) -> AgentState:
    """执行节点：根据配置查询数据，完整暴露 SQL 到 state"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "execute_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    if state.get("intent") == "chat":
        trace.append({"step": "execute_skip", "reason": "chat_intent"})
        state["trace_log"] = trace
        return state

    charts = state.get("charts", [])
    if charts:
        # 多图表：逐个执行
        for chart in charts:
            pc_dict = chart.get("pivot_config") or chart.get("config")
            ct = chart.get("chart_type", "bar")
            if pc_dict:
                pc_dict["chart_type"] = ct
                try:
                    cfg = PivotConfig(**pc_dict)
                    res = execute_pivot(cfg)
                    chart["data"] = res.get("data", [])
                    chart["vega_spec"] = res.get("vega_spec", {})
                    chart["sql"] = res.get("sql")
                except Exception as e2:
                    logger.error("多图表执行失败: %s, config=%s", e2, pc_dict)
                    chart["error"] = str(e2)

        trace.append({"step": "execute_success", "chart_count": len(charts)})
        state["trace_log"] = trace
        return state

    # 单图表（向后兼容）
    pivot_config_dict = state.get("pivot_config")
    if not pivot_config_dict:
        trace.append({"step": "execute_skip", "reason": "no_pivot_config"})
        state["trace_log"] = trace
        return state

    try:
        chart_type = state.get("chart_type", "bar")
        pivot_config_dict["chart_type"] = chart_type
        config = PivotConfig(**pivot_config_dict)
        result = execute_pivot(config)

        state["data"] = result.get("data", [])
        state["vega_spec"] = result.get("vega_spec", {})
        state["sql"] = result.get("sql")

        trace.append({
            "step": "execute_success",
            "timestamp": datetime.now().isoformat(),
            "row_count": len(state["data"]),
            "columns": result.get("columns", []),
            "execution_time_ms": result.get("execution_time_ms"),
            "sql": state["sql"][:500] if state.get("sql") else None,
        })

    except Exception as e:
        logger.error("Agent 查询执行失败: %s", e, exc_info=True)
        state["error"] = (state.get("error") or "") + f" 查询执行失败: {e}"
        if state.get("data") is None:
            state["data"] = []
        if state.get("sql") is None:
            state["sql"] = ""

    trace.append({
        "step": "execute_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


def format_reply_node(state: AgentState) -> AgentState:
    """格式化回复节点：构造最终回复并保存日志"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "format_reply_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    data = state.get("data")
    if data is not None and len(data) > 0:
        state["reply"] += f"\n\n查询到 {len(data)} 条结果。"

    log_path = _save_trace_log(state)
    trace.append({"step": "log_saved", "path": log_path})

    trace.append({
        "step": "format_reply_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


def build_agent() -> Any:
    """构建 LangGraph Agent（两分支：聊天 / 图表分析）"""
    workflow = StateGraph(AgentState)

    workflow.add_node("analyze", analyze_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges(
        "analyze",
        lambda s: "execute" if s.get("intent") == "chart" else "format_reply",
    )
    workflow.add_edge("execute", "format_reply")
    workflow.add_edge("format_reply", END)

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app


# 全局 Agent 实例
_agent = None


def get_agent() -> Any:
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


async def process_chat(message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """处理聊天请求"""
    import uuid
    start = time.time()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "reply": "AI 对话需要配置 OPENAI_API_KEY 环境变量，请先在 .env 文件中设置。",
            "pivot_config": None,
            "vega_spec": {},
            "data": None,
            "sql": None,
            "chart_type": "bar",
            "suggestions": [],
            "execution_time_ms": 0,
        }

    agent = get_agent()
    thread_id = str(uuid.uuid4())

    state: AgentState = {
        "user_message": message,
        "conversation_history": history or [],
        "intent": None,
        "pivot_config": None,
        "chart_type": "bar",
        "charts": [],
        "suggestions": [],
        "sql": None,
        "data": None,
        "vega_spec": None,
        "reply": "",
        "error": None,
        "trace_log": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(state, config)

    elapsed = (time.time() - start) * 1000

    charts = result.get("charts", []) or []
    # 统一返回 charts 列表（单图表也包装成列表）
    if not charts:
        pc = result.get("pivot_config")
        ct = result.get("chart_type", "bar")
        if pc or result.get("intent") == "chart":
            charts = [{
                "title": "",
                "pivot_config": pc,
                "chart_type": ct,
                "data": result.get("data"),
                "sql": result.get("sql"),
            }]

    return {
        "reply": result.get("reply", ""),
        "charts": charts,
        "suggestions": result.get("suggestions", []),
        "execution_time_ms": round(elapsed, 2),
    }
