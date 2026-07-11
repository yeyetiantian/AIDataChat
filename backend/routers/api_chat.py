"""POST /api/chat — AI 对话式分析

接收自然语言，通过 LangGraph Agent 生成配置。
消息持久化存储到 SQLite。
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.pivot_agent import process_chat
from core.chat_db import (
    add_message,
    get_messages,
    get_session,
    create_session,
    update_session_title,
)
from models import ChatResponse

logger = logging.getLogger("api_chat")

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入")
    session_id: Optional[str] = Field(None, description="会话 ID，首次不传自动生成")
    user_id: Optional[int] = Field(None, description="用户 ID，不传则使用内存模式")


@router.post("/chat", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """AI 对话式分析"""
    try:
        # 判断是否使用数据库持久化
        use_db = request.user_id is not None

        # 会话管理
        session_id = request.session_id or str(uuid.uuid4())

        # 如果是 DB 模式，确保会话存在
        if use_db:
            existing = get_session(session_id)
            if not existing:
                create_session(session_id, request.user_id, "新对话", "chart")
            # 从 DB 加载历史消息
            db_messages = get_messages(session_id)
            history = []
            for m in db_messages:
                msg = {"role": m["role"], "content": m["content"]}
                if m.get("charts"):
                    msg["charts"] = m["charts"]
                if m.get("suggestions"):
                    msg["suggestions"] = m["suggestions"]
                history.append(msg)
            # 截断 history 为最近 20 条（避免 token 过长）
            if len(history) > 20:
                history = history[-20:]
        else:
            # 无 user_id 时使用空历史
            history = []

        # 调用 Agent（传入 session_id 用于 trace 关联）
        result = await process_chat(request.message, history, session_id=session_id)

        # 保存用户消息和 AI 回复
        reply = result.get("reply", "")
        charts = result.get("charts", []) or []
        suggestions = result.get("suggestions", []) or []

        if use_db:
            # 自动标题：从第一条用户消息提取
            user_msg_count = len([m for m in db_messages if m["role"] == "user"])
            # 计算包含当前消息后的用户消息数
            user_msg_total = user_msg_count + 1

            add_message(session_id, "user", request.message)
            add_message(session_id, "assistant", reply, charts, suggestions)

            # 如果这是第一条用户消息，自动设置标题
            if user_msg_total == 1:
                title = request.message[:30] + ("..." if len(request.message) > 30 else "")
                update_session_title(session_id, title)
        else:
            pass  # 无 user_id，不持久化

        return ChatResponse(
            reply=reply,
            charts=charts,
            suggestions=suggestions,
            rules=result.get("rules", []) or [],
            session_id=session_id,
            trace_id=result.get("trace_id", ""),
            is_dashboard=result.get("is_dashboard", False),
            charts_count=len(charts),
            execution_time_ms=result.get("execution_time_ms", 0),
            ask_questions=result.get("ask_questions", []) or [],
            pending_step=result.get("pending_step"),
        )
    except Exception as e:
        logger.error("聊天分析失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
