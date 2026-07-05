"""POST /api/chat — AI 对话式分析

接收自然语言，通过 LangGraph Agent 生成配置并查询数据。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agents.pivot_agent import process_chat
from models import ChatRequest, ChatResponse

logger = logging.getLogger("api_chat")

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """AI 对话式分析"""
    try:
        result = await process_chat(request.message, request.history)
        return ChatResponse(**result)
    except Exception as e:
        logger.error("聊天分析失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
