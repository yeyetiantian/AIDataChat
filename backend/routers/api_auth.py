"""用户 API — 仅提供用户列表查询，无登录认证"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from core.chat_db import list_all_users

logger = logging.getLogger("api_auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserResponse(BaseModel):
    id: int
    username: str
    role: str


@router.get("/users", response_model=list[UserResponse])
async def list_users():
    """获取所有用户列表（默认种子用户：管理员、分析员、查看者）"""
    return list_all_users()
