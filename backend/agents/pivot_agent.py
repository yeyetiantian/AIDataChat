"""LangGraph NL2SQL Agent

将用户自然语言转换为 PivotConfig + DuckDB SQL。
需注入大宽表完整 Schema。
保留完整链路日志。
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

# SQL 查询模板名（实际 JOIN 6 张源表）
QUERY_SOURCE = "(6 张源表 LEFT JOIN)"

# Agent 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ---- Agent State ----
class AgentState(TypedDict):
    """Agent 状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    pivot_config: Optional[dict[str, Any]]
    chart_type: Optional[str]
    sql: Optional[str]
    data: Optional[list[dict[str, Any]]]
    vega_spec: Optional[dict[str, Any]]
    reply: str
    error: Optional[str]
    trace_log: list[dict[str, Any]]


def _save_trace_log(state: AgentState, session_id: str = None) -> str:
    """保存 Agent 链路日志到文件"""
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    log_entry = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "user_message": state.get("user_message", ""),
        "pivot_config": state.get("pivot_config"),
        "sql": state.get("sql"),
        "reply": state.get("reply"),
        "error": state.get("error"),
        "trace": state.get("trace_log", []),
    }

    log_path = os.path.join(LOG_DIR, f"agent_{session_id}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
    return log_path


# ---- Agent Nodes ----

def _build_system_prompt() -> str:
    """构建 Agent System Prompt"""
    schema = get_schema_for_agent(top_signals=60)
    return f"""你是一个数据透视分析专家。你的任务是将用户的自然语言分析需求，转换为结构化的透视表配置和 DuckDB SQL。

## 数据库
你的数据来源是明细宽表 **WIDE_DETAIL**，包含以下字段：

{schema}

## 输出要求
你必须输出严格的 JSON 格式，包含以下三个字段：
1. pivot_config：透视表配置（必需）
2. reply：对用户的自然语言回复（必需）
3. chart_type：图表类型，可选值 bar/line/area/point/pie/radar（必需）

### PivotConfig 格式
```json
{{
  "filters": [],
  "axes": [{{"field": "字段名", "alias": "中文别名"}}],
  "legend": [{{"field": "字段名", "alias": "中文别名"}}],
  "values": [{{"id": "val_1", "field": "字段名", "aggregation": "count", "alias": "中文别名"}}],
  "grand_total": false,
  "subtotals": false,
  "limit": 10000
}}
```

### 字段说明
- `axes`: 横轴/行维度字段（GROUP BY）
- `legend`: 图例字段（PIVOT ON，用于多系列对比）
- `values`: 聚合值字段，aggregation 可选: count/sum/avg/min/max/count_distinct
- `filters`: WHERE 筛选条件，op 可选: =/!=/>/>=/</<=/between/in/like
- `chart_type`: 根据数据特点选择:
  - 时间序列 → line/area
  - 类别对比 → bar
  - 占比分析 → pie
  - 多变量 → radar

### SQL 要求
- 固定字段（person/vehicle_type/vehicle/task/rule_name/rule_type/alarm_time/duration_sec）可直接引用
- 对信号列（如 UDat_13、PrplsnSysAtv）做数值聚合时，需要使用 TRY_CAST("信号名" AS DOUBLE)

## 示例
用户问："各车型的报警次数"
回复：
{{
  "pivot_config": {{
    "filters": [],
    "axes": [{{"field": "vehicle_type", "alias": "车型"}}],
    "legend": [],
    "values": [{{"id": "val_1", "field": "alarm_time", "aggregation": "count", "alias": "报警次数"}}],
    "grand_total": true,
    "limit": 10000
  }},
  "reply": "以下是各车型的报警次数统计：",
  "chart_type": "bar"
}}

注意：你的回复必须是合法的 JSON，不要包含 markdown 代码块标记或其他文字。
"""


def analyze_node(state: AgentState) -> AgentState:
    """NL2SQL 分析节点：调用 LLM 生成配置"""
    trace = state.get("trace_log", [])
    trace.append({"step": "analyze_start", "timestamp": datetime.now().isoformat(), "input": state["user_message"]})

    try:
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

        messages = [
            {"role": "system", "content": _build_system_prompt()},
        ]

        # 添加对话历史
        for h in (state.get("conversation_history") or []):
            messages.append(h)

        messages.append({"role": "user", "content": state["user_message"]})

        response = llm.invoke(messages)
        content = response.content.strip()

        trace.append({"step": "llm_response", "timestamp": datetime.now().isoformat(), "raw": content[:500]})

        # 解析 JSON 响应
        result = None
        # 尝试从 markdown 代码块中提取
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                result = json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 如果没找到代码块，尝试直接解析
        if result is None:
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                raise ValueError(f"LLM 返回无法解析为 JSON: {content[:200]}")

        pivot_config_dict = result.get("pivot_config") or result.get("pivotConfig")
        chart_type = result.get("chart_type", "bar")

        # 如果没有 pivot_config，尝试生成一个简单的
        if not pivot_config_dict:
            pivot_config_dict = {
                "filters": [],
                "axes": [],
                "legend": [],
                "values": [],
                "chart_type": chart_type,
            }

        state["pivot_config"] = pivot_config_dict
        state["chart_type"] = chart_type
        state["reply"] = result.get("reply", "已生成分析配置。")
        state["error"] = None

        trace.append({"step": "analyze_success", "timestamp": datetime.now().isoformat(), "has_config": pivot_config_dict is not None})

    except Exception as e:
        logger.error("Agent 分析失败: %s", e, exc_info=True)
        state["error"] = str(e)
        state["reply"] = f"分析时出错：{e}"
        state["chart_type"] = "bar"
        trace.append({"step": "analyze_error", "timestamp": datetime.now().isoformat(), "error": str(e)})

    state["trace_log"] = trace
    return state


def execute_node(state: AgentState) -> AgentState:
    """执行节点：根据配置查询数据"""
    trace = state.get("trace_log", [])
    trace.append({"step": "execute_start", "timestamp": datetime.now().isoformat()})

    pivot_config_dict = state.get("pivot_config")
    if not pivot_config_dict:
        trace.append({"step": "execute_skip", "reason": "no_pivot_config"})
        state["trace_log"] = trace
        return state

    try:
        # 添加 chart_type 到 config
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
            "execution_time_ms": result.get("execution_time_ms"),
        })

    except Exception as e:
        logger.error("Agent 查询执行失败: %s", e, exc_info=True)
        state["error"] = (state.get("error") or "") + f" 查询执行失败: {e}"
        trace.append({"step": "execute_error", "timestamp": datetime.now().isoformat(), "error": str(e)})

    state["trace_log"] = trace
    return state


def format_reply_node(state: AgentState) -> AgentState:
    """格式化回复节点：构造最终回复"""
    trace = state.get("trace_log", [])

    data = state.get("data")
    if data is not None:
        state["reply"] += f"\n\n查询到 {len(data)} 条结果。"

    # 保存链路日志
    log_path = _save_trace_log(state)
    trace.append({"step": "log_saved", "path": log_path})
    state["trace_log"] = trace

    return state


def build_agent() -> Any:
    """构建 LangGraph Agent"""
    workflow = StateGraph(AgentState)

    workflow.add_node("analyze", analyze_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "execute")
    workflow.add_edge("execute", "format_reply")
    workflow.add_edge("format_reply", END)

    # 使用 MemorySaver 保存 checkpoint
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

    # 检查 API Key
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
        "pivot_config": result.get("pivot_config"),
        "vega_spec": result.get("vega_spec", {}),
        "data": result.get("data"),
        "sql": result.get("sql"),
        "chart_type": result.get("chart_type", "bar"),
        "execution_time_ms": round(elapsed, 2),
    }
