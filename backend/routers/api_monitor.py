"""Agent 监控 API — Trace 日志查询 & 流程图数据

提供：
- GET /api/monitor/traces — Trace 摘要列表
- GET /api/monitor/traces/{trace_id} — 完整 Trace 详情（含 root_span_json）
- GET /api/monitor/traces/sessions — 有 Trace 记录的会话列表
- GET /api/monitor/stats — 统计信息
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.chat_db import (
    list_trace_summaries,
    get_trace_detail,
    list_session_ids_for_traces,
    get_trace_stats,
    delete_trace,
    clear_traces,
)

logger = logging.getLogger("api_monitor")

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/traces")
async def get_traces(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session_id: Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
):
    """获取 Trace 摘要列表（不含 root_span_json）"""
    traces = list_trace_summaries(limit=limit, offset=offset, session_id=session_id, agent_name=agent_name)
    return {"traces": traces, "total": len(traces)}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """获取完整 Trace 详情"""
    trace = get_trace_detail(trace_id)
    if not trace:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trace not found")

    # 解析 root_span —— 兼容新格式（root_span dict）和旧格式（root_span_json 字符串）
    root_span = trace.get("root_span") or {}
    if not root_span and trace.get("root_span_json"):
        try:
            root_span = json.loads(trace["root_span_json"])
        except (json.JSONDecodeError, TypeError):
            root_span = {"error": "invalid root_span_json"}

    return {
        "id": trace.get("id", trace.get("trace_id", "")),
        "session_id": trace.get("session_id", ""),
        "request_message": trace.get("request_message", trace.get("user_message", "")),
        "agent_name": trace.get("agent_name", trace.get("agent", "")),
        "status": trace.get("status", ""),
        "created_at": trace.get("created_at", ""),
        "updated_at": trace.get("updated_at", ""),
        "root_span": root_span,
    }


@router.get("/traces/sessions/list")
async def get_trace_sessions(
    limit: int = Query(100, ge=1, le=500),
):
    """获取有 Trace 记录的会话 ID 列表"""
    sessions = list_session_ids_for_traces(limit=limit)
    return {"sessions": sessions}


@router.get("/stats")
async def get_monitor_stats():
    """获取监控统计信息"""
    return get_trace_stats()


@router.delete("/traces/{trace_id}")
async def delete_single_trace(trace_id: str):
    """删除单个 Trace"""
    success = delete_trace(trace_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"success": True, "message": f"Trace {trace_id} 已删除"}


@router.delete("/traces")
async def clear_all_traces(
    agent_name: Optional[str] = Query(None),
):
    """清空所有 Trace，可选按 agent_name 筛选"""
    count = clear_traces(agent_name=agent_name)
    return {"success": True, "message": f"已清空 {count} 条 Trace 日志"}
