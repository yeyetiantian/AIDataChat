"""闲聊子 Agent — chat_reply → format_reply

数据流：
  chat_reply（调用 LLM 生成自然回复）→ format_reply（保存日志）
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, TypedDict

from agents.llm_utils import (
    is_private_provider,
    get_llm,
    save_trace_log,
    TraceCollector,
    SpanNode,
)

logger = logging.getLogger("chat_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# 全局缓存
# ============================================================

_chat_system_prompt: str | None = None


def _get_chat_system_prompt() -> str:
    global _chat_system_prompt
    if _chat_system_prompt is not None:
        return _chat_system_prompt

    _chat_system_prompt = """你是数据分析助手的闲聊模式。请用友好、简洁的方式回答用户的日常问题。
- 如果用户问系统功能，简要介绍你能做的（数据分析、图表推荐、规则查询等）
- 如果用户打招呼，友好回应即可
- 保持回复简短，不超过 3 句话
- 不要编造数据或图表配置
- 不要重复用户的话"""
    return _chat_system_prompt


# ---- Agent State ----
class ChatState(TypedDict):
    """闲聊状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    reply: str
    suggestions: list[str]
    error: str | None

    trace_collector: TraceCollector | None
    trace_span: SpanNode | None


def _save_trace_log(state: ChatState, session_id: str = None) -> str:
    from agents.llm_utils import save_trace_log
    return save_trace_log(
        agent_name="chat_agent",
        state=state,
        session_id=session_id,
    )


# ============================================================
# Agent Nodes
# ============================================================

def chat_reply_node(state: ChatState) -> ChatState:
    """闲聊回复节点：调用 LLM 生成自然对话回复"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child("chat_reply", "llm", input={"message": state["user_message"]}) if (tc and parent_span) else None

    # trace_log 已废弃

    try:
        chat_system_prompt = _get_chat_system_prompt()
        llm = get_llm()
        messages = [{"role": "system", "content": chat_system_prompt}]
        history = [h for h in (state.get("conversation_history") or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        raw_resp = llm.invoke(messages)
        reply = raw_resp.content.strip() if hasattr(raw_resp, 'content') else str(raw_resp)

        state["reply"] = reply
        state["suggestions"] = []
        if sp:
            sp.messages = messages
            sp.tokens = {"input": -1, "output": -1}
            sp.finish(output={"reply": reply[:500]})


    except Exception as e:
        logger.error("闲聊回复失败: %s", e, exc_info=True)
        state["reply"] = "抱歉，我现在有点忙，请稍后再试。"
        state["error"] = str(e)
        if sp:
            sp.finish(error=str(e))



    return state


def format_reply_node(state: ChatState) -> ChatState:
    """格式化回复节点：构造最终回复并保存日志"""
    tc: TraceCollector | None = state.get("trace_collector")

    # trace_log 已废弃

    if tc:
        if state.get("error"):
            tc.root.finish(error=state["error"])
        else:
            tc.root.finish(output={"reply": state.get("reply", "")[:200]})

    log_path = _save_trace_log(state)
    return state


# ============================================================
# Agent 构建
# ============================================================

def build_chat_agent() -> Any:
    """构建闲聊 Agent

    数据流：
      chat_reply → format_reply
    """
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(ChatState)
    workflow.add_node("chat_reply", chat_reply_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("chat_reply")
    workflow.add_edge("chat_reply", "format_reply")
    workflow.add_edge("format_reply", END)

    return workflow.compile()


async def process_chat(message: str, history: list[dict[str, str]] | None = None, session_id: str | None = None) -> dict[str, Any]:
    """处理闲聊请求"""
    import uuid
    import time

    start = time.time()

    tc = TraceCollector(
        session_id=session_id or "",
        request_message=message,
        agent_name="chat_agent",
    )

    agent = build_chat_agent()
    thread_id = str(uuid.uuid4())

    state: ChatState = {
        "user_message": message,
        "conversation_history": history or [],
        "reply": "",
        "suggestions": [],
        "error": None,
        "trace_collector": tc,
        "trace_span": tc.root,
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(state, config)

    tc.save_to_db()

    elapsed = (time.time() - start) * 1000

    return {
        "reply": result.get("reply", ""),
        "charts": [],
        "suggestions": [],
        "rules": [],
        "trace_id": tc.trace_id,
        "execution_time_ms": round(elapsed, 2),
    }
