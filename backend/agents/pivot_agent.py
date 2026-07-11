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

import json
import logging
import os
import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from agents.llm_utils import (
    is_private_provider,
    get_llm,
    get_structured_llm,
    try_parse_json,
)

logger = logging.getLogger("pivot_agent")

# ============================================================
# Structured Output 模型
# ============================================================

class IntentOutput(BaseModel):
    """意图识别输出"""
    intent: Literal["chat", "chart", "rule", "dashboard"] = Field(
        description="用户意图: chat=闲聊, chart=图表分析, rule=规则函数推荐"
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
                    intent=intent_val if intent_val in ("chat", "chart", "rule", "dashboard") else "chat",
                    reason=result.get("reason", ""),
                )

        return response.intent, response.reason

    except Exception as e:
        logger.error("意图识别失败: %s", e, exc_info=True)
        return "chat", f"意图识别失败: {e}"

# ============================================================
# 主入口
# ============================================================

async def process_chat(message: str, history: list[dict[str, str]] | None = None, session_id: str | None = None) -> dict[str, Any]:
    """处理聊天请求 — 意图识别后分发到子 Agent

    Args:
        message: 用户消息
        history: 对话历史 [{role: "user"/"assistant", content: "..."}]

    Returns:
        {reply, charts, suggestions, rules, execution_time_ms}
    """
    start = time.time()

    # 检查认证配置
    if is_private_provider():
        if not os.getenv("PRIVATE_LLM_CLIENT_ID") or not os.getenv("PRIVATE_LLM_TOKEN_URL"):
            return {
                "reply": "私有 LLM 需要配置 PRIVATE_LLM_CLIENT_ID / PRIVATE_LLM_TOKEN_URL 环境变量",
                "charts": [],
                "suggestions": [],
                "rules": [],
                "execution_time_ms": 0,
            }
    elif not os.getenv("OPENAI_API_KEY"):
        return {
            "reply": "AI 对话需要配置 OPENAI_API_KEY 环境变量，请先在 .env 文件中设置。",
            "charts": [],
            "suggestions": [],
            "rules": [],
            "execution_time_ms": 0,
        }

    # 1. 意图识别
    intent, reason = _recognize_intent(message, history)
    logger.info("意图识别: %s (%s)", intent, reason)

    # 2. 分发到子 Agent（传入 session_id 供 trace 采集）
    if intent == "chart" or intent == "dashboard":
        from agents.chart_agent import process_chart as chart_process
        result = await chart_process(message, history, session_id=session_id)
    elif intent == "rule":
        from agents.rule_agent import process_rule as rule_process
        result = await rule_process(message, history, session_id=session_id)
    else:  # chat
        from agents.chat_agent import process_chat as chat_process
        result = await chat_process(message, history, session_id=session_id)

    elapsed = (time.time() - start) * 1000
    result["execution_time_ms"] = round(elapsed, 2)
    return result

