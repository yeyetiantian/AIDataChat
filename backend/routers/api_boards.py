"""看板管理 API — 多看板 CRUD（SQLite 持久化）"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.chat_db import (
    list_boards, get_board, create_board, update_board, delete_board,
)

logger = logging.getLogger("api_boards")
router = APIRouter(prefix="/api/boards", tags=["boards"])


class BoardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=500)
    user_id: int = Field(1, description="创建人")


class BoardUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=500)


class BoardResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str
    created_at: str
    updated_at: str


@router.get("", response_model=list[BoardResponse])
async def get_boards(user_id: int = Query(1, description="用户 ID")):
    """获取用户的所有看板"""
    return list_boards(user_id)


@router.post("", response_model=BoardResponse)
async def create_new_board(board: BoardCreate):
    """创建看板"""
    result = create_board(
        user_id=board.user_id,
        name=board.name,
        description=board.description,
    )
    logger.info("看板已创建: id=%s name=%s", result["id"], board.name)
    return result


@router.get("/{board_id}", response_model=BoardResponse)
async def get_single_board(board_id: int):
    b = get_board(board_id)
    if not b:
        raise HTTPException(status_code=404, detail="看板不存在")
    return b


@router.put("/{board_id}", response_model=BoardResponse)
async def update_single_board(board_id: int, board: BoardUpdate):
    result = update_board(
        board_id=board_id,
        name=board.name,
        description=board.description,
    )
    if not result:
        raise HTTPException(status_code=404, detail="看板不存在")
    return result


@router.delete("/{board_id}")
async def remove_board(board_id: int):
    ok = delete_board(board_id)
    if not ok:
        raise HTTPException(status_code=404, detail="看板不存在")
    return {"success": True}
