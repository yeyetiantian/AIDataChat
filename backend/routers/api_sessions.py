"""会话管理 API"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.chat_db import (
    list_sessions,
    get_session,
    create_session,
    update_session_title,
    delete_session,
    get_messages,
)

logger = logging.getLogger("api_sessions")
router = APIRouter(prefix="/api/chat", tags=["sessions"])


class SessionCreateRequest(BaseModel):
    user_id: int = Field(1, description="用户 ID")
    title: str = Field("新对话", description="会话标题")
    mode: str = Field("chart", description="模式: chart/rule")


class SessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="新标题")


class SessionResponse(BaseModel):
    id: str
    user_id: int
    title: str
    mode: str
    created_at: str = ""
    updated_at: str = ""


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    charts: list = []
    suggestions: list = []
    created_at: str = ""


@router.get("/sessions", response_model=list[SessionResponse])
async def get_sessions(user_id: int = Query(1, description="用户 ID")):
    """获取用户的所有会话"""
    return list_sessions(user_id)


@router.post("/sessions", response_model=SessionResponse)
async def create_new_session(req: SessionCreateRequest):
    """创建新会话"""
    session_id = str(uuid.uuid4())
    session = create_session(session_id, req.user_id, req.title, req.mode)
    # Re-fetch to get timestamps
    full = get_session(session_id)
    return full or session


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def rename_session(session_id: str, req: SessionRenameRequest):
    """重命名会话"""
    existing = get_session(session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="会话不存在")
    update_session_title(session_id, req.title)
    return get_session(session_id)


@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str):
    """删除会话及其所有消息"""
    existing = get_session(session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="会话不存在")
    delete_session(session_id)
    return {"success": True}


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session_id: str):
    """获取会话的消息列表"""
    return get_messages(session_id)
