"""POST /api/chat — AI 对话式分析

接收自然语言，通过 LangGraph Agent 生成配置。
消息持久化存储到 SQLite。
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.pivot_agent import process_chat, process_chat_stream
from core.chat_db import (
    add_message,
    clear_draft_message,
    get_messages,
    get_session,
    create_session,
    update_session_title,
    save_agent_draft,
)
from models import ChatResponse, DashboardRequestDraft

logger = logging.getLogger("api_chat")

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入")
    session_id: Optional[str] = Field(None, description="会话 ID，首次不传自动生成")
    user_id: Optional[int] = Field(None, description="用户 ID，不传则使用内存模式")
    task_id: Optional[int] = Field(None, description="规则配置推荐可选任务 ID")
    dashboard_draft: Optional[DashboardRequestDraft] = Field(None, description="结构化看板问卷草案")


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

        dashboard_draft = request.dashboard_draft
        dashboard_draft_id = ""
        if dashboard_draft is not None:
            dashboard_draft_id = save_agent_draft(
                session_id, "dashboard", dashboard_draft.model_dump(mode="json"), dashboard_draft.draft_id,
            )
            dashboard_draft.draft_id = dashboard_draft_id

        # 调用 Agent（传入 session_id 用于 trace 关联）
        result = await process_chat(
            request.message, history, session_id=session_id, task_id=request.task_id,
            dashboard_draft=dashboard_draft.model_dump(mode="json") if dashboard_draft else None,
        )

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
            add_message(session_id, "assistant", reply, charts, suggestions,
                        ask_questions=result.get("ask_questions", []),
                        pending_step=result.get("pending_step"),
                        rules=result.get("rules", []),
                        query_result=result.get("query_result"))

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
            dashboard_draft_id=dashboard_draft_id,
            query_result=result.get("query_result"),
        )
    except Exception as e:
        logger.error("聊天分析失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_query_stream(request: ChatRequest):
    """流式 AI 对话分析 — 通过 SSE 实时推送思考过程"""
    use_db = request.user_id is not None
    session_id = request.session_id or str(uuid.uuid4())

    # 会话管理（同常规端点）
    if use_db:
        existing = get_session(session_id)
        if not existing:
            create_session(session_id, request.user_id, "新对话", "chart")
        db_messages = get_messages(session_id)
        history = []
        for m in db_messages:
            msg = {"role": m["role"], "content": m["content"]}
            if m.get("charts"):
                msg["charts"] = m["charts"]
            if m.get("suggestions"):
                msg["suggestions"] = m["suggestions"]
            history.append(msg)
        if len(history) > 20:
            history = history[-20:]
    else:
        history = []

    dashboard_draft_data = None
    dashboard_draft_id = ""
    if request.dashboard_draft is not None:
        dashboard_draft_data = request.dashboard_draft.model_dump(mode="json")
        dashboard_draft_id = save_agent_draft(
            session_id, "dashboard", dashboard_draft_data, request.dashboard_draft.draft_id,
        )

    async def event_stream():
        from agents.stream_utils import complete_event as sse_complete

        full_result = {}
        user_msg_count = 0

        async for sse_event in process_chat_stream(
            request.message, history, session_id=session_id,
            task_id=request.task_id,
            dashboard_draft=dashboard_draft_data,
        ):
            yield sse_event

            # 拦截 complete 事件提取完整结果用于持久化
            if sse_event.startswith("event: complete"):
                import json as _json
                prefix = "data: "
                for line in sse_event.split("\n"):
                    if line.startswith(prefix):
                        full_result = _json.loads(line[len(prefix):])

        # 持久化（流结束后）
        if use_db and full_result:
            reply = full_result.get("reply", "")
            charts = full_result.get("charts", []) or []
            suggestions = full_result.get("suggestions", []) or []

            # 计算用户消息数（用于自动标题）
            existing_msgs = get_messages(session_id)
            user_msg_count = len([m for m in existing_msgs if m["role"] == "user"])

            add_message(session_id, "user", request.message)
            add_message(session_id, "assistant", reply, charts, suggestions,
                        ask_questions=full_result.get("ask_questions", []),
                        pending_step=full_result.get("pending_step"),
                        rules=full_result.get("rules", []),
                        query_result=full_result.get("query_result"))

            # 首次用户消息自动设置标题
            if user_msg_count == 1 or (user_msg_count == 0 and len(existing_msgs) == 0):
                title = request.message[:30] + ("..." if len(request.message) > 30 else "")
                update_session_title(session_id, title)

            # 看板问卷提交后，清理之前的草案消息
            if request.dashboard_draft is not None:
                cleared = clear_draft_message(
                    session_id,
                    new_content="看板需求已确认，问卷信息已提交，正在生成本地...",
                )
                if cleared:
                    logger.info("已清理看板草案消息 (session=%s)", session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "session-id": session_id,
        },
    )


@router.post("/chat/cancel-draft")
async def cancel_draft(session_id: str):
    """取消看板问卷，清除 DB 中的草案消息"""
    cleared = clear_draft_message(
        session_id,
        new_content="⚠️ 看板问卷已取消",
    )
    return {"success": cleared, "session_id": session_id}
