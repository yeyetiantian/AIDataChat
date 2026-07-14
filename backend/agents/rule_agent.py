"""规则配置推荐子 Agent — 根据用户输入推荐合适的函数和信号。

数据流：
  analyze_rule（LLM 基于数据库中的函数/信号列表推荐）→ format_reply
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from agents.llm_utils import (
    get_llm,
    get_structured_llm,
    save_trace_log,
    try_parse_json,
    SpanNode,
    TraceCollector,
)

logger = logging.getLogger("rule_agent")


class FunctionRecommendation(BaseModel):
    """推荐的函数"""
    name: str = Field(description="函数名称，如 abs(signal1)")
    description: str = Field("", description="函数功能简述")
    applicable_signals: list[str] = Field(default_factory=list, description="适用的信号名称列表")
    usage_example: str = Field("", description="使用示例")
    reason: str = Field("", description="推荐理由")


class AgentOutput(BaseModel):
    """LLM 结构化输出"""
    reply: str = Field(description="给用户的推荐说明")
    recommendations: list[FunctionRecommendation] = Field(default_factory=list)


_RULE_SYSTEM_PROMPT = """你是企业车辆数据系统的函数配置推荐助手。

根据用户的需求，从下方提供的函数库中推荐最合适的函数，同时推荐该函数适用的业务信号。

约束：
1. 只能引用下方提供的函数，不得编造不存在的函数。
2. 函数推荐需说明推荐理由和使用示例。
3. 如果用户需求与现有函数无法匹配，如实告知。
4. reply 字段只写一句简短的回复（如"为您推荐以下函数："），不要重复函数详情，函数详情会通过卡片独立展示。
"""

class RuleState(TypedDict):
    user_message: str
    conversation_history: list[dict[str, str]]
    reply: str
    rule_recommendations: list[dict[str, Any]]
    error: str | None
    trace_collector: TraceCollector | None
    trace_span: SpanNode | None


def _get_functions_context() -> str:
    """从数据库读取函数列表，构建 LLM 上下文。"""
    from core.chat_db import list_freeze_functions, _get_conn

    lines = ["## 可用函数库\n"]
    functions = list_freeze_functions(deleted=False)
    if functions:
        for f in functions:
            name = f.get("name", "")
            desc = f.get("description", "")
            params = f.get("params", "")
            returns = f.get("returns", "")
            parts = [f"- `{name}`"]
            if desc:
                parts.append(f"  功能：{desc}")
            if params:
                parts.append(f"  入参：{params}")
            if returns:
                parts.append(f"  出参：{returns}")
            lines.append("\n".join(parts))
    else:
        lines.append("暂无可用函数。")

    return "\n".join(lines)


def analyze_rule_node(state: RuleState) -> RuleState:
    """根据用户输入和函数库，推荐合适的函数和信号。"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child("analyze_rule", "llm", input={"message": state["user_message"]}) if (tc and parent_span) else None

    try:
        functions_context = _get_functions_context()
        system_prompt = f"{_RULE_SYSTEM_PROMPT}\n\n{functions_context}"
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in state.get("conversation_history") or []:
            role, content = item.get("role"), item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": state["user_message"]})

        response: AgentOutput | None = None
        structured_llm = get_structured_llm(AgentOutput)
        if structured_llm is not None:
            try:
                response = structured_llm.invoke(messages)
            except Exception as exc:
                logger.warning("StructuredOutput 失败，回退解析：%s", exc)

        if response is None:
            parser = PydanticOutputParser(pydantic_object=AgentOutput)
            fallback_messages = [{"role": "system", "content": f"{system_prompt}\n\n{parser.get_format_instructions()}"}] + messages[1:]
            raw = get_llm().invoke(fallback_messages)
            raw_content = raw.content.strip() if hasattr(raw, "content") else str(raw)
            try:
                response = parser.parse(raw_content)
            except Exception:
                parsed = try_parse_json(raw_content) or {}
                try:
                    response = AgentOutput.model_validate(parsed)
                except Exception:
                    response = AgentOutput(reply="暂时无法解析推荐结果，请稍后重试。")

        state["reply"] = response.reply
        state["rule_recommendations"] = [r.model_dump() for r in response.recommendations]

        if sp:
            sp.messages = messages
            sp.tokens = {"input": -1, "output": -1}
            sp.finish(output={"recommendations": len(state["rule_recommendations"])})
    except Exception as exc:
        logger.exception("规则推荐分析失败")
        state["error"] = str(exc)
        state["reply"] = "分析失败，请稍后重试。"
        state["rule_recommendations"] = []
        if sp:
            sp.finish(error=str(exc))
    return state


def format_reply_node(state: RuleState) -> RuleState:
    tc = state.get("trace_collector")
    if tc:
        if state.get("error"):
            tc.root.finish(error=state["error"])
        else:
            tc.root.finish(output={"reply": state.get("reply", "")[:200], "recommendations": len(state.get("rule_recommendations", []))})
    _save_trace_log(state)
    return state


def _save_trace_log(state: RuleState, session_id: str | None = None) -> str:
    recommendations = state.get("rule_recommendations", []) or []
    return save_trace_log(
        agent_name="rule_agent",
        state=state,
        extra={"rule_recommendation_count": len(recommendations)},
        session_id=session_id,
    )


def build_rule_agent() -> Any:
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(RuleState)
    workflow.add_node("analyze_rule", analyze_rule_node)
    workflow.add_node("format_reply", format_reply_node)
    workflow.set_entry_point("analyze_rule")
    workflow.add_edge("analyze_rule", "format_reply")
    workflow.add_edge("format_reply", END)
    return workflow.compile()


async def process_rule(
    message: str,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    task_id: int | None = None,
) -> dict[str, Any]:
    """处理规则推荐请求。"""
    import time
    import uuid

    started_at = time.time()
    collector = TraceCollector(session_id=session_id or "", request_message=message, agent_name="rule_agent")
    state: RuleState = {
        "user_message": message,
        "conversation_history": history or [],
        "reply": "",
        "rule_recommendations": [],
        "error": None,
        "trace_collector": collector,
        "trace_span": collector.root,
    }
    result = await build_rule_agent().ainvoke(state, {"configurable": {"thread_id": str(uuid.uuid4())}})
    collector.save_to_db()
    return {
        "reply": result.get("reply", ""),
        "rules": result.get("rule_recommendations", []) or [],
        "trace_id": collector.trace_id,
        "execution_time_ms": round((time.time() - started_at) * 1000, 2),
    }
