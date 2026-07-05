"""LangGraph NL2SQL Agent

将用户自然语言转换为 PivotConfig + DuckDB SQL。
需注入大宽表完整 Schema。
保留完整链路日志（每个节点的原始输入/输出）。

优化：
- 全局单例 ChatOpenAI，避免每次请求创建新实例
- 全局缓存 schema + system prompt 基础内容
- 支持对话上下文迭代：二次追问修正图表（加筛选、改图表类型等）
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from core.db_connector import get_conn
from core.field_registry import get_schema_for_agent
from core.pivot_sql_builder import execute_pivot
from models import PivotConfig

logger = logging.getLogger("pivot_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# 全局缓存（单例）
# ============================================================

_llm: Optional[ChatOpenAI] = None
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
    _base_system_prompt = f"""你是数据分析助手，支持两种模式：普通聊天 和 数据图表分析。

## 数据库
你的数据来源是明细宽表 **WIDE_DETAIL**，包含以下字段：

{schema}

## 行为规则
根据用户的问题，决定输出格式：

### 1. 普通聊天模式
如果用户只是打招呼、问简单问题，直接回复即可。
输出格式：
{{"intent": "chat", "reply": "你的回复内容"}}

### 2. 图表分析模式（含迭代修正）
如果用户想要统计、分析、查看图表，或者对已有图表进行修正，
必须输出完整的 JSON 配置用于生成图表。

**支持用户自定义筛选和二次追问修正：**
- 用户可以说"只看SUV的" → 在 filters 中添加筛选条件
- 用户可以说"改成折线图" → 修改 chart_type
- 用户可以说"按天统计" → 在 axes 的 field 上添加 group
- 用户可以说"再加个图例按规则名称" → 在 legend 中添加字段

**对话历史中的前一次 pivot_config 可作为基础进行迭代修改。**
检查 conversation_history 中的上一次 assistant 回复，
提取其中的 pivot_config 做增量修改，而不是每次都从头生成。

输出格式：
{{{{
  "intent": "chart",
  "pivot_config": {{{{
    "filters": [{{{{"field": "字段名", "op": "操作符", "value": 值}}}}],
    "axes": [{{{{"field": "字段名", "alias": "中文别名"}}}}],
    "legend": [{{{{"field": "字段名", "alias": "中文别名"}}}}],
    "values": [{{{{"id": "val_1", "field": "字段名", "aggregation": "count", "alias": "中文别名"}}}}],
    "grand_total": false,
    "subtotals": false,
    "limit": 10000
  }}}},
  "reply": "对结果的文字说明",
  "chart_type": "bar"
}}}}

### 字段说明
- axes: 横轴/行维度字段（GROUP BY）
- legend: 图例字段（PIVOT ON，用于多系列对比）
- values: 聚合值字段，aggregation 可选: count/sum/avg/min/max/count_distinct
- filters: WHERE 筛选条件，op 可选: =/!=/>/>=/</<=/between/in/like
- chart_type: 根据数据特点选择: bar/line/area/point/pie/radar
- group: 时间粒度，可选 year/quarter/month/week/day/hour（仅用于时间字段）

### 自定义筛选示例
用户（第一次）："各车型报警次数"
回复：chart pivot_config（无 filters）

用户（第二次）："只看SUV的数据"
回复：chart pivot_config（在第一次的基础上，filters 增加 [{{{{"field": "vehicle_type", "op": "=", "value": "SUV"}}}}]）

用户（第三次）："改成折线图"
回复：chart pivot_config（保持 filters 和 axes 不变，chart_type 改为 line）

### SQL 要求
- 固定字段（person/vehicle_type/vehicle/task/rule_name/rule_type/alarm_time/duration_sec）可直接引用
- 对信号列（如 IBSBatSOC、PrplsnSysAtv）做数值聚合时，使用 TRY_CAST("信号名" AS DOUBLE)

注意：必须输出纯 JSON，不要包含 markdown 代码块标记或其他文字。"""

    return _base_system_prompt


# ---- Agent State ----
class AgentState(TypedDict):
    """Agent 状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    intent: Optional[str]               # "chart" | "chat"
    pivot_config: Optional[dict[str, Any]]
    chart_type: Optional[str]
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
        "reply": state.get("reply"),
        "error": state.get("error"),
        "trace": state.get("trace_log", []),
    }

    log_path = os.path.join(LOG_DIR, f"agent_{session_id}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
    return log_path


# ---- Agent Nodes ----

def analyze_node(state: AgentState) -> AgentState:
    """NL2SQL 分析节点：调用 LLM 生成配置（支持上下文迭代）"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "analyze_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    try:
        llm = _get_llm()

        messages = [
            {"role": "system", "content": _get_base_system_prompt()},
        ]
        # 添加上下文对话历史
        for h in (state.get("conversation_history") or []):
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        response = llm.invoke(messages)
        content = response.content.strip()

        trace.append({
            "step": "llm_raw_response",
            "timestamp": datetime.now().isoformat(),
            "raw_output": content[:1000],
        })

        # 解析 JSON
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

        intent = result.get("intent", "chart")

        if intent == "chat":
            state["intent"] = "chat"
            state["reply"] = result.get("reply", "")
            state["pivot_config"] = None
            state["chart_type"] = "bar"
            state["error"] = None
            trace.append({"step": "analyze_complete", "timestamp": datetime.now().isoformat(), "intent": "chat"})
        else:
            state["intent"] = "chart"
            pivot_config_dict = result.get("pivot_config") or result.get("pivotConfig")
            chart_type = result.get("chart_type", "bar")
            state["pivot_config"] = pivot_config_dict
            state["chart_type"] = chart_type
            state["reply"] = result.get("reply", "已生成分析配置。")
            state["error"] = None
            trace.append({
                "step": "analyze_complete",
                "timestamp": datetime.now().isoformat(),
                "intent": "chart",
                "has_config": pivot_config_dict is not None,
            })

    except Exception as e:
        logger.error("Agent 分析失败: %s", e, exc_info=True)
        state["error"] = str(e)
        state["reply"] = f"分析时出错：{e}"
        state["chart_type"] = "bar"
        trace.append({"step": "analyze_error", "timestamp": datetime.now().isoformat(), "error": str(e)})

    trace.append({
        "step": "analyze_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


def execute_node(state: AgentState) -> AgentState:
    """执行节点：根据配置查询数据"""
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

        trace.append({
            "step": "execute_success",
            "timestamp": datetime.now().isoformat(),
            "row_count": len(state["data"]),
            "columns": result.get("columns", []),
            "execution_time_ms": result.get("execution_time_ms"),
        })
    except Exception as e:
        logger.error("Agent 查询执行失败: %s", e, exc_info=True)
        state["error"] = (state.get("error") or "") + f" 查询执行失败: {e}"
        trace.append({
            "step": "execute_error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        })

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

    return {
        "reply": result.get("reply", ""),
        "pivot_config": result.get("pivot_config") if result.get("intent") == "chart" else None,
        "vega_spec": result.get("vega_spec") or {},
        "data": result.get("data"),
        "sql": result.get("sql"),
        "chart_type": result.get("chart_type", "bar"),
        "execution_time_ms": round(elapsed, 2),
    }
