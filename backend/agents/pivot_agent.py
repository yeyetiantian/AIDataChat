"""LangGraph AI 分析与图表配置主 Agent

将用户自然语言分发到三个子 Agent：
  - chart_agent: 图表分析（analyze → validate → execute → format_reply）
  - rule_agent: 规则函数推荐（analyze_rule → format_reply）
  - chat_agent: 闲聊回复（chat_reply → format_reply）

数据流：
  intent_recognition → 路由:
    chart → chart_agent.process_chart()
    rule  → rule_agent.process_rule()
    chat  → chat_agent.process_chat()
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from agents.llm_utils import (
    get_llm,
    get_structured_llm,
    try_parse_json,
    TraceCollector,
    SpanNode,
)

logger = logging.getLogger("pivot_agent")

# ============================================================
# Structured Output 模型
# ============================================================

class IntentOutput(BaseModel):
    """意图识别输出"""
    intent: Literal["chat", "chart", "rule", "dashboard", "dtc"] = Field(
        description="用户意图: chat=闲聊, chart=图表分析, rule=规则函数推荐, dtc=DTC故障码查询"
    )
    reason: str = Field("", description="意图判断原因")

# ============================================================
# 全局缓存
# ============================================================

_intent_system_prompt: str | None = None

def _get_intent_system_prompt() -> str:
    """意图识别 prompt（轻量，仅分类）"""
    global _intent_system_prompt
    if _intent_system_prompt is not None:
        return _intent_system_prompt

    _intent_system_prompt = """你是数据分析系统的意图识别器。请判断用户的输入属于以下哪种意图：

- chart: 用户想要查看数据、生成图表、分析趋势、做数据对比等数据可视化或数据查询需求
- dashboard: 用户想要创建看板、数据大屏、多图表看板，或一次查看多个维度的数据
- rule: 用户想要了解规则函数、规则配置、规则说明、规则功能解释等规则相关信息
- dtc: 用户想要查询 DTC 故障码、诊断数据、车辆故障信息、dtc_info 表或 dtc_trigger 表中的数据
- chat: 普通问候、闲聊、或不属于以上两类的其他问题

## 示例

用户输入: "你好"            → {"intent": "chat", "reason": "普通问候"}
用户输入: "各车型报警次数"   → {"intent": "chart", "reason": "用户想按车型统计报警数据"}
用户输入: "速度规则有哪些"   → {"intent": "rule", "reason": "用户想查询速度相关的规则函数"}
用户输入: "帮我分析下最近一周的报警趋势" → {"intent": "chart", "reason": "用户想做时间趋势分析"}
用户输入: "什么是超速规则"   → {"intent": "rule", "reason": "用户想了解超速规则的定义"}
用户输入: "帮我创建一个看板" → {"intent": "dashboard", "reason": "用户想创建多图表看板"}
用户输入: "做一个数据大屏展示所有维度的报警情况" → {"intent": "dashboard", "reason": "用户想要一个包含多个图表的大屏看板"}
用户输入: "我要同时看各车型违规次数和规则类型占比" → {"intent": "dashboard", "reason": "用户一次想看多个维度的图表，适合创建看板"}
用户输入: "查询VIN为LSGNB8P58TS061027的DTC故障码" → {"intent": "dtc", "reason": "用户想查询特定车辆的DTC故障码数据"}
用户输入: "看看U0104故障码都出现在哪些车上" → {"intent": "dtc", "reason": "用户想查询特定DTC故障码的车辆分布"}
用户输入: "DTC触发记录有哪些" → {"intent": "dtc", "reason": "用户想查看DTC触发记录数据"}
用户输入: "最近一周的DTC报警统计" → {"intent": "dtc", "reason": "用户想查询DTC报警的时间统计"}

请直接返回意图标签和简要原因。"""
    return _intent_system_prompt

# ============================================================
# 意图识别
# ============================================================

def _recognize_intent(message: str, history: list[dict[str, str]] | None = None) -> tuple[str, str]:
    """识别用户意图，返回 (intent, reason)"""
    try:
        from langchain_core.output_parsers import PydanticOutputParser

        system_prompt = _get_intent_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        history = [h for h in (history or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": message})

        # 尝试 structured output
        structured_llm = get_structured_llm(IntentOutput)
        response: IntentOutput | None = None

        if structured_llm is not None:
            try:
                response = structured_llm.invoke(messages)
            except Exception:
                logger.warning("Intent StructuredOutput 失败，使用 PydanticOutputParser 兜底")
                response = None

        if response is None:
            parser = PydanticOutputParser(pydantic_object=IntentOutput)
            messages[0] = {
                "role": "system",
                "content": f"{system_prompt}\n\n## 输出格式\n{parser.get_format_instructions()}",
            }
            raw_resp = get_llm().invoke(messages)
            try:
                response = parser.parse(raw_resp.content.strip())
            except Exception:
                result = try_parse_json(raw_resp.content.strip()) or {}
                intent_val = result.get("intent", "chat")
                response = IntentOutput(
                    intent=intent_val if intent_val in ("chat", "chart", "rule", "dashboard", "dtc") else "chat",
                    reason=result.get("reason", ""),
                )

        return response.intent, response.reason

    except Exception as e:
        logger.error("意图识别失败: %s", e, exc_info=True)
        return "chat", f"意图识别失败: {e}"

# ============================================================
# 主入口
# ============================================================

async def process_chat(
    message: str,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    task_id: int | None = None,
    dashboard_draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """处理聊天请求 — 意图识别后分发到子 Agent

    创建全链路 TraceCollector，覆盖意图识别 → 子 Agent 执行 → 结果返回 的完整路径。
    """
    start = time.time()

    # 创建全链路 TraceCollector（从接口层开始，覆盖意图识别→子Agent→返回）
    tc = TraceCollector(
        session_id=session_id or "",
        request_message=message,
        agent_name="pivot_agent",
    )
    tc.root.input = {
        "api": "POST /api/chat",
        "message": message,
        "session_id": session_id,
        "history_count": len(history or []),
        "task_id": task_id,
        "has_dashboard_draft": dashboard_draft is not None,
    }

    # 1. 意图识别（独立 span，记录完整输入/输出）
    intent_span = tc.root.add_child("intent_recognition", "llm", input={"message": message})
    intent, reason = _recognize_intent(message, history)
    intent_span.finish(output={"intent": intent, "reason": reason})
    logger.info("意图识别: %s (%s)", intent, reason)

    # 2. 分发到子 Agent（传入 tc 实现全链路追踪）
    if intent == "chart":
        from agents.chart_agent import process_chart as chart_process
        result = await chart_process(
            message, history, session_id=session_id,
            trace_collector=tc, parent_span=tc.root,
        )
    elif intent == "dashboard":
        from agents.dashboard_agent import process_dashboard
        result = await process_dashboard(
            message, history, session_id=session_id, intent=intent, dashboard_draft=dashboard_draft,
            trace_collector=tc, parent_span=tc.root,
        )
    elif intent == "rule":
        from agents.rule_agent import process_rule as rule_process
        result = await rule_process(
            message, history, session_id=session_id, task_id=task_id,
            trace_collector=tc, parent_span=tc.root,
        )
    elif intent == "dtc":
        from agents.dtc_agent import process_dtc as dtc_process
        result = await dtc_process(
            message, history, session_id=session_id,
            trace_collector=tc, parent_span=tc.root,
        )
    else:  # chat
        from agents.chat_agent import process_chat as chat_process
        result = await chat_process(
            message, history, session_id=session_id,
            trace_collector=tc, parent_span=tc.root,
        )

    # 3. 完成根 span 并保存完整 trace
    elapsed = (time.time() - start) * 1000
    tc.root.finish(output={
        **result,
        "execution_time_ms": round(elapsed, 2),
    })
    tc.save_to_db()

    result["execution_time_ms"] = round(elapsed, 2)
    result["trace_id"] = tc.trace_id
    return result
