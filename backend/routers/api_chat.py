"""POST /api/chat — AI 对话式分析

接收自然语言，通过 LangGraph Agent 生成配置并查询数据。
维护内存会话上下文（单次会话内记忆，不持久化）。
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException

from agents.pivot_agent import process_chat
from models import ChatRequest, ChatResponse

logger = logging.getLogger("api_chat")

router = APIRouter(prefix="/api", tags=["chat"])

# 内存会话存储（key=session_id, value=消息历史）
# 仅在内存中保留，服务重启后清空
_sessions: dict[str, list[dict[str, str]]] = {}


@router.post("/chat", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """AI 对话式分析"""
    try:
        # 会话管理：首次请求自动生成 session_id
        session_id = request.session_id or str(uuid.uuid4())

        # 加载历史消息
        history = _sessions.get(session_id, [])

        # 调用 Agent
        result = await process_chat(request.message, history)

        # 保存本轮对话到内存
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": result.get("reply", "")})
        _sessions[session_id] = history

        return ChatResponse(
            reply=result.get("reply", ""),
            charts=result.get("charts", []) or [],
            suggestions=result.get("suggestions", []),
            session_id=session_id,
            execution_time_ms=result.get("execution_time_ms", 0),
        )
    except Exception as e:
        logger.error("聊天分析失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
