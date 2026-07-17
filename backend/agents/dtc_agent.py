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
    """LLM 生成的 SQL 查询（同时查两张表）"""
    sql_dtc_info: str = Field("", description="dtc_info 表的 SQL 查询语句（仅 SELECT）")
    sql_dtc_trigger: str = Field("", description="dtc_trigger 表的 SQL 查询语句（仅 SELECT）")
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
        # 复用 chat_db 的共享连接（避免多连接锁冲突）
        from core.chat_db import _get_conn
        conn = _get_conn()
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

        _TABLE_SCHEMA = "\n".join(lines)
        logger.info("DTC 表结构已构建: %d chars", len(_TABLE_SCHEMA))
    except Exception as e:
        logger.warning("读取 DTC 表结构失败: %s", e)
        # 错误不缓存，下次重试
        return "无法读取表结构信息。"

    return _TABLE_SCHEMA


# ============================================================
# System Prompt
# ============================================================

_DTC_SYSTEM_PROMPT = """你是 DTC（Diagnostic Trouble Code）数据查询助手。

你的任务是根据用户的问题，为 dtc_info 和 dtc_trigger 两张表各生成一条 SQL 查询语句，同时查询两张表的数据并返回。

## 表结构

{table_schema}

## 生成 SQL 约束

1. 必须同时为 `dtc_info` 和 `dtc_trigger` 两张表**各生成一条 SQL**（即使只和一张表相关，也要生成另一张表的兜底查询）
2. 只生成 SELECT 语句（不允许修改数据）
3. VIN 字段是字符串类型，查询时需要用引号括起来
4. 时间字段是字符串类型，直接用 `>=` / `<=` 比较即可
5. 如果用户请求模糊不清，可以适当猜测合理条件，并在 explanation 中说明
6. 每条 SQL 都要加 LIMIT 1000 防止数据量过大

## 返回格式

必须返回结构化 JSON：
- sql_dtc_info: dtc_info 表的 SQL 语句（如果无关可设为 "SELECT * FROM dtc_info LIMIT 1000"）
- sql_dtc_trigger: dtc_trigger 表的 SQL 语句（如果无关可设为 "SELECT * FROM dtc_trigger LIMIT 1000"）
- explanation: 用中文解释这条查询在查什么，以及查询条件说明
- reply: 给用户的简短回复，说明已经理解需求并开始查询
"""


def _get_system_prompt() -> str:
    return _DTC_SYSTEM_PROMPT.format(table_schema=_get_table_schema())


# ============================================================
# Agent State
# ============================================================

class DtcState(TypedDict):
    """DTC 查询 Agent 状态（同时查询两张表）"""
    user_message: str
    conversation_history: list[dict[str, str]]
    generated_sql_info: str
    generated_sql_trigger: str
    sql_explanation: str
    query_result_info: dict[str, Any] | None
    query_result_trigger: dict[str, Any] | None
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
            "sql_info": state.get("generated_sql_info", ""),
            "sql_trigger": state.get("generated_sql_trigger", ""),
            "result_info_total": (state.get("query_result_info") or {}).get("total", 0),
            "result_trigger_total": (state.get("query_result_trigger") or {}).get("total", 0),
        },
    )


def analyze_dtc_node(state: DtcState) -> DtcState:
    """分析用户输入，为两张表各生成一条 SQL 查询"""
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
                        sql_dtc_info="SELECT * FROM dtc_info LIMIT 1000",
                        sql_dtc_trigger="SELECT * FROM dtc_trigger LIMIT 1000",
                        explanation="无法解析 LLM 输出，使用默认查询",
                        reply="已为您查询 DTC 数据，请稍候...",
                    )

        state["generated_sql_info"] = response.sql_dtc_info
        state["generated_sql_trigger"] = response.sql_dtc_trigger
        state["sql_explanation"] = response.explanation
        state["reply"] = response.explanation

        if sp:
            sp.messages = messages
            sp.finish(output={
                "sql_dtc_info": response.sql_dtc_info,
                "sql_dtc_trigger": response.sql_dtc_trigger,
                "explanation": response.explanation,
            })

    except Exception as exc:
        logger.exception("DTC 分析失败")
        state["error"] = str(exc)
        state["reply"] = "分析失败，请稍后重试。"
        state["generated_sql_info"] = ""
        state["generated_sql_trigger"] = ""
        if sp:
            sp.finish(error=str(exc))

    return state


def _execute_single_sql(sql: str, label: str, sp: SpanNode | None) -> dict[str, Any] | None:
    """执行单条 SQL，返回结构化结果或 None"""
    sql = sql.strip()
    if not sql:
        return None

    # SQL 安全校验
    if not sql.upper().startswith("SELECT"):
        logger.warning("[%s] 非 SELECT 语句被拦截: %.100s", label, sql)
        return None
    dangerous = ["DELETE", "DROP", "INSERT", "UPDATE", "ALTER", "CREATE", "PRAGMA", "ATTACH"]
    upper_sql = sql.upper()
    import re
    for kw in dangerous:
        if re.search(rf"\b{re.escape(kw)}\b", upper_sql):
            logger.warning("[%s] 含危险关键字 %s: %.100s", label, kw, sql)
            return None

    try:
        from core.chat_db import _get_conn
        conn = _get_conn()
        cursor = conn.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        columns = [desc[0] for desc in cursor.description]
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "total": len(rows),
            "sql": sql,
        }
    except Exception as exc:
        logger.error("[%s] 查询执行失败: %s", label, exc)
        return {"success": False, "error": str(exc), "sql": sql}


def execute_dtc_node(state: DtcState) -> DtcState:
    """执行两张表的 SQL 查询"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child(
        "execute_dtc", "api", input={
            "sql_info": state.get("generated_sql_info", ""),
            "sql_trigger": state.get("generated_sql_trigger", ""),
        }
    ) if (tc and parent_span) else None

    result_info = _execute_single_sql(state.get("generated_sql_info", ""), "dtc_info", sp)
    result_trigger = _execute_single_sql(state.get("generated_sql_trigger", ""), "dtc_trigger", sp)

    state["query_result_info"] = result_info if (result_info and result_info.get("success")) else None
    state["query_result_trigger"] = result_trigger if (result_trigger and result_trigger.get("success")) else None

    if not result_info and not result_trigger:
        state["error"] = "两张表查询均失败"

    if sp:
        sp.finish(output={
            "info_total": (result_info or {}).get("total", 0),
            "trigger_total": (result_trigger or {}).get("total", 0),
        })

    return state


def format_reply_node(state: DtcState) -> DtcState:
    """格式化最终回复（包含两张表的结果）"""
    tc: TraceCollector | None = state.get("trace_collector")
    result_info = state.get("query_result_info")
    result_trigger = state.get("query_result_trigger")

    if state.get("error") and not result_info and not result_trigger:
        error_msg = state["error"]
        state["reply"] = error_msg
        if tc:
            tc.root.finish(error=error_msg)
    else:
        parts = []
        if result_info:
            parts.append(f"📋 dtc_info 表：查得 {result_info['total']} 条记录")
        if result_trigger:
            parts.append(f"📋 dtc_trigger 表：查得 {result_trigger['total']} 条记录")
        reply_text = state.get("reply") or "查询完成。"
        state["reply"] = f"已为您查询两张表的数据：\n" + "\n".join(parts) + f"\n\n{reply_text}"

        if tc:
            tc.root.finish(output={
                "reply": state.get("reply", ""),
                "info_total": (result_info or {}).get("total", 0),
                "trigger_total": (result_trigger or {}).get("total", 0),
            })

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
        "generated_sql_info": "",
        "generated_sql_trigger": "",
        "sql_explanation": "",
        "query_result_info": None,
        "query_result_trigger": None,
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
            "sql_info": result.get("generated_sql_info", ""),
            "sql_trigger": result.get("generated_sql_trigger", ""),
            "result_info_total": (result.get("query_result_info") or {}).get("total", 0),
            "result_trigger_total": (result.get("query_result_trigger") or {}).get("total", 0),
        })

    # 构造返回数据（包含两张表的结果）
    result_info = result.get("query_result_info")
    result_trigger = result.get("query_result_trigger")

    query_results = {}
    if result_info:
        query_results["info"] = {
            "table": "dtc_info",
            "sql": result.get("generated_sql_info", ""),
            "columns": result_info.get("columns", []),
            "rows": result_info.get("rows", []),
            "total": result_info.get("total", 0),
        }
    if result_trigger:
        query_results["trigger"] = {
            "table": "dtc_trigger",
            "sql": result.get("generated_sql_trigger", ""),
            "columns": result_trigger.get("columns", []),
            "rows": result_trigger.get("rows", []),
            "total": result_trigger.get("total", 0),
        }

    return {
        "reply": result.get("reply", ""),
        "charts": [],
        "suggestions": [],
        "rules": [],
        "query_result": query_results if query_results else None,
        "trace_id": tc.trace_id,
        "execution_time_ms": round((time.time() - started_at) * 1000, 2),
    }