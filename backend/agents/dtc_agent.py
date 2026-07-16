"""DTC 数据查询子 Agent — analyze → execute → format_reply

数据流：
  analyze_dtc（LLM 基于表结构生成 SQL）→ execute_dtc（调用 /api/dtc/query 执行）
    → format_reply（包装结果返回）

注意事项：
  - 只能通过 HTTP 调用 /api/dtc/query 接口执行 SQL，不可直连数据库
  - 后续可替换为外部 API 地址
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, TypedDict

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

logger = logging.getLogger("dtc_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)

# DTC 查询接口地址（默认本地 8000，可通过 DTC_API_URL 环境变量覆盖）
_DEFAULT_PORT = os.getenv("PORT", "8000")
_DEFAULT_HOST = os.getenv("HOST", "127.0.0.1")
_DTC_API_URL = os.getenv("DTC_API_URL", f"http://{_DEFAULT_HOST}:{_DEFAULT_PORT}/api/dtc/query")


# ============================================================
# Structured Output 模型
# ============================================================

class DtcSqlOutput(BaseModel):
    """LLM 生成的 SQL 查询"""
    sql: str = Field(..., description="生成的 SQL 查询语句（仅 SELECT）")
    explanation: str = Field("", description="SQL 查询的解释说明，用中文告诉用户这条 SQL 在查什么")
    reply: str = Field("", description="给用户的自然语言回复，简述查询结果概览")


# ============================================================
# 表结构上下文（Agent 启动时构建一次）
# ============================================================

_TABLE_SCHEMA: str | None = None


def _get_table_schema() -> str:
    """从数据库读取 dtc_info / dtc_trigger 的表结构，构建 LLM 上下文"""
    global _TABLE_SCHEMA
    if _TABLE_SCHEMA is not None:
        return _TABLE_SCHEMA

    try:
        import sqlite3
        import sys
        _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(_backend_dir, "ai_data.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        lines = [
            "## DTC 数据表结构（仅用于参考，Agent 不可直连数据库，必须通过 API 查询）",
            "",
        ]

        for table in ("dtc_info", "dtc_trigger"):
            cursor.execute(f"PRAGMA table_info([{table}])")
            cols = cursor.fetchall()
            lines.append(f"### 表名: {table}")
            lines.append("| 列名 | 类型 | 说明 |")
            lines.append("|------|------|------|")
            for col in cols:
                name = col[1]
                col_type = col[2]
                # 简单说明
                desc = ""
                name_lower = name.lower()
                if "vin" in name_lower:
                    desc = "车辆识别码"
                elif "time" in name_lower or "date" in name_lower:
                    desc = "时间字段"
                elif "code" in name_lower:
                    desc = "故障码 / 事件码"
                elif "lat" in name_lower:
                    desc = "GPS 纬度"
                elif "lon" in name_lower:
                    desc = "GPS 经度"
                elif "des" in name_lower or "desc" in name_lower or "message" in name_lower or "str" in name_lower:
                    desc = "描述信息"
                elif "id" in name_lower:
                    desc = "唯一标识"
                elif "type" in name_lower or "status" in name_lower:
                    desc = "类型 / 状态"
                elif "channel" in name_lower:
                    desc = "通道"
                elif "protocol" in name_lower:
                    desc = "协议"
                elif "ecu" in name_lower:
                    desc = "ECU 名称"
                elif "fault" in name_lower:
                    desc = "故障类型"
                elif "event" in name_lower:
                    desc = "事件名称"
                elif "gps" in name_lower:
                    desc = "GPS 坐标"
                elif "source" in name_lower:
                    desc = "数据来源"
                elif "rmu" in name_lower:
                    desc = "RMU 编码"
                elif "trigger" in name_lower:
                    desc = "触发标识"
                lines.append(f"| {name} | {col_type} | {desc} |")
            lines.append("")

        # 添加示例数据
        for table in ("dtc_info", "dtc_trigger"):
            cursor.execute(f"SELECT * FROM [{table}] LIMIT 3")
            sample_rows = cursor.fetchall()
            col_names = [d[0] for d in cursor.description]
            lines.append(f"### {table} 示例数据（3 行）")
            lines.append(f"列: {', '.join(col_names)}")
            for row in sample_rows:
                truncated = [str(v)[:40] if v is not None else "NULL" for v in row]
                lines.append(f"  {', '.join(truncated)}")
            lines.append("")

        conn.close()
        _TABLE_SCHEMA = "\n".join(lines)
        logger.info("DTC 表结构已构建: %d chars", len(_TABLE_SCHEMA))
    except Exception as e:
        logger.warning("读取 DTC 表结构失败: %s", e)
        _TABLE_SCHEMA = "无法读取表结构信息。"

    return _TABLE_SCHEMA


# ============================================================
# System Prompt
# ============================================================

_DTC_SYSTEM_PROMPT = """你是 DTC（Diagnostic Trouble Code）数据查询助手。

你的任务是根据用户的问题，生成 SQL 查询语句来查询 DTC 数据。

## 表结构

{table_schema}

## 生成 SQL 约束

1. 只能查询 `dtc_info` 和 `dtc_trigger` 两张表
2. 只生成 SELECT 语句（不允许修改数据）
3. VIN 字段是字符串类型，查询时需要用引号括起来
4. 时间字段是字符串类型，直接用 `>=` / `<=` 比较即可
5. 如果查询涉及多表关联，使用 JOIN（dtc_info 和 dtc_trigger 可通过 VIN + RMU_CODE 关联）
6. 如果用户请求模糊不清，可以适当猜测合理条件，并在 explanation 中说明

## 返回格式

必须返回结构化 JSON：
- sql: 生成的 SQL 语句
- explanation: 用中文解释这条 SQL 在查什么，以及查询条件说明
- reply: 给用户的简短回复，说明已经理解需求并开始查询
"""


def _get_system_prompt() -> str:
    return _DTC_SYSTEM_PROMPT.format(table_schema=_get_table_schema())


# ============================================================
# Agent State
# ============================================================

class DtcState(TypedDict):
    """DTC 查询 Agent 状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    generated_sql: str
    sql_explanation: str
    query_result: dict[str, Any] | None
    reply: str
    error: str | None

    trace_collector: TraceCollector | None
    trace_span: SpanNode | None


# ============================================================
# Agent Nodes
# ============================================================

def _save_trace_log(state: DtcState, session_id: str = None) -> str:
    return save_trace_log(
        agent_name="dtc_agent",
        state=state,
        session_id=session_id,
        extra={
            "sql": state.get("generated_sql", ""),
            "result_total": (state.get("query_result") or {}).get("total", 0),
        },
    )


def analyze_dtc_node(state: DtcState) -> DtcState:
    """分析用户输入，生成 SQL 查询"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child(
        "analyze_dtc", "llm", input={"message": state["user_message"]}
    ) if (tc and parent_span) else None

    try:
        system_prompt = _get_system_prompt()
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in state.get("conversation_history") or []:
            role, content = item.get("role"), item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": state["user_message"]})

        # 尝试结构化输出
        response: DtcSqlOutput | None = None
        structured_llm = get_structured_llm(DtcSqlOutput)
        if structured_llm is not None:
            try:
                response = structured_llm.invoke(messages)
            except Exception as exc:
                logger.warning("DTC StructuredOutput 失败，回退解析: %s", exc)

        # 兜底：PydanticOutputParser + 手动 JSON 解析
        if response is None:
            from langchain_core.output_parsers import PydanticOutputParser
            parser = PydanticOutputParser(pydantic_object=DtcSqlOutput)
            fallback_messages = [
                {"role": "system", "content": f"{system_prompt}\n\n{parser.get_format_instructions()}"}
            ] + messages[1:]
            raw = get_llm().invoke(fallback_messages)
            raw_content = raw.content.strip() if hasattr(raw, "content") else str(raw)
            try:
                response = parser.parse(raw_content)
            except Exception:
                parsed = try_parse_json(raw_content) or {}
                try:
                    response = DtcSqlOutput.model_validate(parsed)
                except Exception:
                    response = DtcSqlOutput(
                        sql="SELECT * FROM dtc_info LIMIT 100",
                        explanation="无法解析 LLM 输出，使用默认查询",
                        reply="已为您查询 DTC 数据，请稍候...",
                    )

        state["generated_sql"] = response.sql
        state["sql_explanation"] = response.explanation
        state["reply"] = response.explanation

        if sp:
            sp.messages = messages
            sp.finish(output={"sql": response.sql, "explanation": response.explanation})

    except Exception as exc:
        logger.exception("DTC 分析失败")
        state["error"] = str(exc)
        state["reply"] = "分析失败，请稍后重试。"
        state["generated_sql"] = ""
        if sp:
            sp.finish(error=str(exc))

    return state


def execute_dtc_node(state: DtcState) -> DtcState:
    """执行 SQL 查询 — 直连数据库执行，不通过 HTTP 自调用（避免死锁）"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child(
        "execute_dtc", "api", input={"sql": state.get("generated_sql", "")}
    ) if (tc and parent_span) else None

    sql = state.get("generated_sql", "").strip()
    if not sql:
        state["error"] = state.get("error") or "未生成 SQL 语句"
        if sp:
            sp.finish(error=state["error"])
        return state

    # SQL 安全校验（复用 api_dtc_query 的规则）
    if not sql.upper().startswith("SELECT"):
        state["error"] = "只允许 SELECT 查询"
        if sp:
            sp.finish(error=state["error"])
        return state
    dangerous = ["DELETE", "DROP", "INSERT", "UPDATE", "ALTER", "CREATE", "PRAGMA", "ATTACH"]
    upper_sql = sql.upper()
    for kw in dangerous:
        import re
        if re.search(rf"\b{re.escape(kw)}\b", upper_sql):
            state["error"] = f"查询中包含不允许的关键字: {kw}"
            if sp:
                sp.finish(error=state["error"])
            return state

    try:
        import sqlite3
        import sys
        if getattr(sys, "frozen", False):
            _backend_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(_backend_dir, "ai_data.db")

        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            rows = [dict(row) for row in cursor.fetchall()]
            columns = [desc[0] for desc in cursor.description]
            state["query_result"] = {
                "success": True,
                "columns": columns,
                "rows": rows,
                "total": len(rows),
            }
            if sp:
                sp.finish(output={
                    "total": len(rows),
                    "columns": columns,
                })
        except sqlite3.Error as e:
            error_msg = f"查询参数有误，请调整后重试。{e}"
            logger.error("DTC 查询执行失败: %s", error_msg)
            state["error"] = error_msg
            state["query_result"] = None
            if sp:
                sp.finish(error=error_msg)
        finally:
            conn.close()

    except Exception as exc:
        error_msg = f"DTC 查询异常，请稍后重试。{exc}"
        logger.error("DTC 查询执行失败: %s", exc)
        state["error"] = error_msg
        state["query_result"] = None
        if sp:
            sp.finish(error=error_msg)

    return state


def format_reply_node(state: DtcState) -> DtcState:
    """格式化最终回复"""
    tc: TraceCollector | None = state.get("trace_collector")
    result = state.get("query_result")

    if state.get("error"):
        error_msg = state["error"]
        state["reply"] = error_msg
        if tc:
            tc.root.finish(error=error_msg)
    elif result:
        total = result.get("total", 0)
        reply_text = state.get("reply") or "查询完成。"
        state["reply"] = f"已为您查询到结果：\n{reply_text}"

        if tc:
            tc.root.finish(output={
                "reply": state.get("reply", ""),
                "total": total,
            })
    else:
        state["reply"] = state.get("reply") or "查询完成，但未返回数据。"
        if tc:
            tc.root.finish(output={"reply": state.get("reply", "")})

    _save_trace_log(state)
    return state


# ============================================================
# Agent 构建
# ============================================================

def build_dtc_agent() -> Any:
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(DtcState)
    workflow.add_node("analyze_dtc", analyze_dtc_node)
    workflow.add_node("execute_dtc", execute_dtc_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("analyze_dtc")
    workflow.add_edge("analyze_dtc", "execute_dtc")
    workflow.add_edge("execute_dtc", "format_reply")
    workflow.add_edge("format_reply", END)

    return workflow.compile()


# ============================================================
# 入口函数
# ============================================================

async def process_dtc(
    message: str,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    trace_collector: TraceCollector | None = None,
    parent_span: SpanNode | None = None,
) -> dict[str, Any]:
    """处理 DTC 数据查询请求

    Args:
        trace_collector: 来自 pivot_agent 的 TraceCollector
        parent_span: 父级 Span
    """
    started_at = time.time()

    if trace_collector and parent_span:
        tc = trace_collector
        agent_span = parent_span.add_child(
            "dtc_agent", "agent",
            input={"message": message},
        )
    else:
        tc = TraceCollector(
            session_id=session_id or "",
            request_message=message,
            agent_name="dtc_agent",
        )
        agent_span = tc.root

    state: DtcState = {
        "user_message": message,
        "conversation_history": history or [],
        "generated_sql": "",
        "sql_explanation": "",
        "query_result": None,
        "reply": "",
        "error": None,
        "trace_collector": tc,
        "trace_span": agent_span,
    }

    result = await build_dtc_agent().ainvoke(
        state,
        {"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    if trace_collector is None:
        tc.save_to_db()
    else:
        agent_span.finish(output={
            "reply": result.get("reply", ""),
            "sql": result.get("generated_sql", ""),
            "result_total": (result.get("query_result") or {}).get("total", 0),
        })

    # 构造返回数据
    query_result = result.get("query_result")
    return {
        "reply": result.get("reply", ""),
        "charts": [],
        "suggestions": [],
        "rules": [],
        "query_result": {
            "sql": result.get("generated_sql", ""),
            "explanation": result.get("sql_explanation", ""),
            "columns": (query_result or {}).get("columns", []),
            "rows": (query_result or {}).get("rows", []),
            "total": (query_result or {}).get("total", 0),
        } if query_result else None,
        "trace_id": tc.trace_id,
        "execution_time_ms": round((time.time() - started_at) * 1000, 2),
    }