"""SSE 流式事件工具 — Agent 思考过程推送"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator


# ============================================================
# 事件类型常量
# ============================================================

EVENT_THINKING = "thinking"
EVENT_COMPLETE = "complete"
EVENT_ERROR = "error"


def format_sse(event: str, data: Any) -> str:
    """将事件格式化为 SSE 文本"""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def thinking_event(node: str, status: str, label: str = "", detail: str = "") -> str:
    """构造思考过程事件

    Args:
        node: 节点标识（如 intent, chart_agent, execute）
        status: pending | running | done | error
        label: 显示标签
        detail: 详细说明
    """
    return format_sse(EVENT_THINKING, {
        "node": node,
        "status": status,
        "label": label,
        "detail": detail,
    })


def complete_event(result: dict[str, Any]) -> str:
    """构造完成事件（最终结果）"""
    return format_sse(EVENT_COMPLETE, result)


def error_event(message: str) -> str:
    """构造错误事件"""
    return format_sse(EVENT_ERROR, {"message": message})


async def stream_agent_events(
    steps: list[dict[str, Any]],
    final_result: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """通用的 Agent 流式事件生成器

    steps: [
        {"node": "intent", "label": "分析意图"},
        {"node": "chart_agent", "label": "生成图表配置"},
    ]
    """
    for step in steps:
        yield thinking_event(step["node"], "running", step["label"], "")
        # 模拟进度（实际由各 Agent 自行 yield）
        yield thinking_event(step["node"], "done", step["label"], step.get("detail", ""))

    yield complete_event(final_result)
