"""规则函数推荐子 Agent — analyze_rule → format_reply

数据流：
  analyze_rule（LLM 生成规则推荐）→ format_reply（格式化回复）
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, TypedDict

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from agents.llm_utils import (
    is_private_provider,
    get_llm,
    get_structured_llm,
    try_parse_json,
    save_trace_log,
    TraceCollector,
    SpanNode,
)

logger = logging.getLogger("rule_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Structured Output 模型
# ============================================================

class RuleRecommendation(BaseModel):
    """规则函数推荐项"""
    rule_name: str = Field(..., description="规则名称")
    rule_type: str | None = Field(None, description="规则类型")
    description: str = Field("", description="规则功能描述")
    priority: str | None = Field(None, description="优先级/重要程度")


class AgentOutput(BaseModel):
    """LLM 结构化输出"""
    intent: str = "rule"
    reply: str = Field(description="回复内容")
    rules: list[RuleRecommendation] = Field(default_factory=list, description="规则函数推荐列表")
    suggestions: list[str] = Field(default_factory=list, description="建议用户追问的 3 个问题")


# ============================================================
# 全局缓存
# ============================================================

_rule_system_prompt: str | None = None











def _get_rule_system_prompt() -> str:
    global _rule_system_prompt
    if _rule_system_prompt is not None:
        return _rule_system_prompt

    _rule_system_prompt = """你是规则函数推荐助手，根据用户的需求推荐合适的规则函数。

## 规则函数分类

### 1. 速度类规则
- 超速规则（Over Speed）：检测车辆超过设定速度阈值
- 区域限速规则（Zone Speed Limit）：特定区域内速度限制
- 平均速度规则（Average Speed）：检测路段平均速度是否超标

### 2. 驾驶行为类规则
- 急加速规则（Hard Acceleration）：检测短时间内速度急剧上升
- 急减速规则（Hard Braking）：检测短时间内速度急剧下降
- 急转弯规则（Sharp Turn）：检测横向加速度超标的转弯
- 疲劳驾驶规则（Drowsy Driving）：检测连续驾驶时间过长
- 分心驾驶规则（Distracted Driving）：检测驾驶分心行为

### 3. 时间类规则
- 定时触发规则（Time Trigger）：在特定时间点触发
- 持续时长规则（Duration）：检测事件持续超过设定时长
- 频率规则（Frequency）：检测单位时间内事件发生频率

### 4. 地理围栏类规则
- 电子围栏规则（Geo-fence）：检测车辆进出特定区域
- 路线偏离规则（Route Deviation）：检测车辆偏离规划路线

## 输出要求
- rule_name: 规则函数名称
- rule_type: 规则类型分类
- description: 规则功能详细说明
- priority: 推荐优先级（high / medium / low）

请根据用户的需求推荐最合适的规则函数，给出每个规则的功能说明和推荐理由。"""
    return _rule_system_prompt


# ---- Agent State ----
class RuleState(TypedDict):
    """规则推荐状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    reply: str
    rule_recommendations: list[dict[str, Any]]
    suggestions: list[str]
    error: str | None

    trace_collector: TraceCollector | None
    trace_span: SpanNode | None


# ---- JSON 解析辅助 ----

def try_parse_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    cleaned = text.replace("{{", "{").replace("}}", "}")
    if cleaned != text:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
    return None


def _save_trace_log(state: RuleState, session_id: str = None) -> str:
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    rules = state.get("rule_recommendations", []) or []

    log_entry = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "user_message": state.get("user_message", ""),
        "reply": state.get("reply"),
        "rule_count": len(rules),
        "rules": rules,
        "error": state.get("error"),
        "trace": state.get("trace_log", []),
    }

    log_path = os.path.join(LOG_DIR, f"rule_agent_{session_id}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
    return log_path


# ============================================================
# Agent Nodes
# ============================================================

def analyze_rule_node(state: RuleState) -> RuleState:
    """规则函数推荐节点：调用 LLM 生成规则推荐"""
    tc: TraceCollector | None = state.get("trace_collector")
    parent_span: SpanNode | None = state.get("trace_span")
    sp: SpanNode | None = parent_span.add_child("analyze_rule", "llm", input={"message": state["user_message"]}) if (tc and parent_span) else None

    trace = state.get("trace_log", [])
    try:
        system_prompt = _get_rule_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        history = [h for h in (state.get("conversation_history") or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        structured_llm = get_structured_llm(AgentOutput)
        response: AgentOutput | None = None

        if structured_llm is not None:
            try:
                response = structured_llm.invoke(messages)
                if sp and response:
                    sp.messages = messages
                    sp.tokens = {"input": -1, "output": -1}
                    sp.output = response.model_dump()
            except Exception:
                response = None

        if response is None:
            parser = PydanticOutputParser(pydantic_object=AgentOutput)
            messages[0] = {"role": "system", "content": f"{system_prompt}\n\n## 输出格式\n{parser.get_format_instructions()}"}
            raw_resp = get_llm().invoke(messages)
            raw_content = raw_resp.content.strip()

            try:
                response = parser.parse(raw_content)
            except Exception as parse_err:
                logger.error("规则推荐 PydanticOutputParser 解析失败: %s", parse_err)
                result = try_parse_json(raw_content)
                response = AgentOutput(
                    intent="rule",
                    reply=result.get("reply", str(parse_err)),
                    rules=[],
                    suggestions=result.get("suggestions", []),
                )

        if sp:
            sp.messages = messages
            sp.tokens = {"input": -1, "output": -1}
            if not sp.output:
                sp.output = response.model_dump()
        state["reply"] = response.reply
        state["suggestions"] = response.suggestions or []
        state["rule_recommendations"] = [
            r.model_dump() if hasattr(r, "model_dump") else r for r in (response.rules or [])
        ]

    except Exception as e:
        logger.error("规则推荐分析失败: %s", e, exc_info=True)
        state["error"] = str(e)
        state["reply"] = f"规则推荐分析时出错：{e}"
        state["rule_recommendations"] = []
        if sp:
            sp.finish(error=str(e))

    if sp and state.get("error") is None and sp.status == "in_progress":
        sp.finish(output={"reply_preview": state.get("reply", "")[:100], "rules": len(state.get("rule_recommendations", []))})
    elif span and state.get("error"):
        sp.finish(error=state.get("error"))
    state["trace_log"] = trace
    return state


def format_reply_node(state: RuleState) -> RuleState:
    """格式化回复节点：构造最终回复并保存日志"""
    # trace_log 已废弃

    # 规则函数推荐：格式化规则列表到回复
    rules = state.get("rule_recommendations", []) or []
    if rules:
        rule_lines = ["为你推荐以下规则函数：\n"]
        for i, r in enumerate(rules, 1):
            name = r.get("rule_name", "未命名")
            desc = r.get("description", "")
            rtype = r.get("rule_type", "")
            priority = r.get("priority", "")
            rule_lines.append(f"{i}. **{name}**")
            if rtype:
                rule_lines.append(f"   - 类型：{rtype}")
            if priority:
                rule_lines.append(f"   - 优先级：{priority}")
            if desc:
                rule_lines.append(f"   - 说明：{desc}")
        rule_text = "\n".join(rule_lines)
        if not state.get("reply"):
            state["reply"] = rule_text
        elif state.get("reply") and rule_text not in state["reply"]:
            state["reply"] += "\n\n" + rule_text

    # 标记 root span 完成
    tc: TraceCollector | None = state.get("trace_collector")
    if tc:
        if state.get("error"):
            tc.root.finish(error=state["error"])
        else:
            tc.root.finish(output={"reply": state.get("reply", "")[:200], "rules": len(state.get("rule_recommendations", []))})

    log_path = _save_trace_log(state)
    return state


# ============================================================
# Agent 构建
# ============================================================

def build_rule_agent() -> Any:
    """构建规则推荐 Agent

    数据流：
      analyze_rule → format_reply
    """
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(RuleState)
    workflow.add_node("analyze_rule", analyze_rule_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("analyze_rule")
    workflow.add_edge("analyze_rule", "format_reply")
    workflow.add_edge("format_reply", END)

    return workflow.compile()


async def process_rule(message: str, history: list[dict[str, str]] | None = None, session_id: str | None = None) -> dict[str, Any]:
    """处理规则推荐请求"""
    import uuid
    import time

    start = time.time()

    tc = TraceCollector(
        session_id=session_id or "",
        request_message=message,
        agent_name="rule_agent",
    )

    agent = build_rule_agent()
    thread_id = str(uuid.uuid4())

    state: RuleState = {
        "user_message": message,
        "conversation_history": history or [],
        "reply": "",
        "rule_recommendations": [],
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
        "rules": result.get("rule_recommendations", []) or [],
        "suggestions": result.get("suggestions", []),
        "trace_id": tc.trace_id,
        "execution_time_ms": round(elapsed, 2),
    }
