"""数据冻结函数 API — CRUD + 软删除 + 任务/规则/信号参考数据"""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.chat_db import (
    list_freeze_functions,
    get_freeze_function,
    soft_delete_freeze_function,
    restore_freeze_function,
    _get_conn,
)

logger = logging.getLogger("api_functions")
router = APIRouter(prefix="/api/functions", tags=["functions"])


class FunctionResponse(BaseModel):
    id: int
    name: str
    description: str = ""
    params: str = ""
    returns: str = ""
    example: str = ""
    func_type: str = ""
    context: str = ""
    remark: str = ""
    needs_improvement: bool = False
    is_deleted: bool = False
    created_at: str = ""
    updated_at: str = ""


@router.get("", response_model=list[FunctionResponse])
async def get_functions():
    """获取所有数据冻结函数（不含已删除的）"""
    return list_freeze_functions(deleted=False)


@router.get("/all", response_model=list[FunctionResponse])
async def get_all_functions():
    """获取所有数据冻结函数（含已删除的）"""
    return list_freeze_functions(deleted=True)


# ====== 参考数据（任务/规则/信号）===== 必须在参数化路由之前注册 ======


class TaskItem(BaseModel):
    TASK_ID: int
    TASK_NAME: str = ""


class RuleItem(BaseModel):
    TASK_RULE_ID: int
    TASK_ID: int | None = None
    RULE_NAME: str = ""


class SignalItem(BaseModel):
    signal_name: str
    signal_type: int = 0
    rule_ids: list[int] = []
    task_ids: list[int] = []
    alarm_count: int = 0
    sample_count: int = 0
    data_status: str = "unavailable"
    updated_at: str | None = None


@router.get("/tasks", response_model=list[TaskItem])
async def get_reference_tasks(keyword: str = Query("", description="搜索关键词")):
    """获取所有任务（下拉选择用，支持关键词搜索）"""
    conn = _get_conn()
    if keyword:
        kw = f"%{keyword}%"
        rows = conn.execute(
            "SELECT TASK_ID, TASK_NAME FROM ext_tasks WHERE (IS_DELETE IS NULL OR IS_DELETE = 0) AND (TASK_NAME LIKE ? OR CAST(TASK_ID AS TEXT) LIKE ?) ORDER BY TASK_ID",
            (kw, kw),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT TASK_ID, TASK_NAME FROM ext_tasks WHERE (IS_DELETE IS NULL OR IS_DELETE = 0) ORDER BY TASK_ID",
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/rules", response_model=list[RuleItem])
async def get_reference_rules(task_id: int | None = Query(None, description="按任务ID筛选"), keyword: str = Query("", description="搜索关键词")):
    """获取所有规则（下拉选择用，支持任务筛选和关键词搜索）"""
    conn = _get_conn()
    where = []
    params = []
    if task_id is not None:
        where.append("TASK_ID = ?")
        params.append(task_id)
    if keyword:
        where.append("(RULE_NAME LIKE ? OR CAST(TASK_RULE_ID AS TEXT) LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])
    sql = "SELECT TASK_RULE_ID, TASK_ID, RULE_NAME FROM ext_rules"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY TASK_RULE_ID"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/signals", response_model=list[SignalItem])
async def get_reference_signals(task_id: int | None = Query(None, description="按任务ID筛选"), rule_id: int | None = Query(None, description="按规则ID筛选"), keyword: str = Query("", description="搜索关键词")):
    """获取所有信号（下拉选择用，支持任务/规则筛选和关键词搜索）"""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT ss.signal_name, ss.signal_type, ss.task_rule_id, ss.alarm_count, ss.sample_count, ss.data_status, ss.updated_at, er.TASK_ID
        FROM signal_stats ss
        LEFT JOIN ext_rules er ON ss.task_rule_id = er.TASK_RULE_ID
    """).fetchall()
    signal_map: dict[str, dict] = defaultdict(lambda: {"rule_ids": set(), "task_ids": set(), "alarms": 0, "samples": 0, "statuses": set(), "updated_at": None})
    for r in rows:
        name = r["signal_name"]
        signal_map[name]["rule_ids"].add(r["task_rule_id"])
        if r["TASK_ID"]:
            signal_map[name]["task_ids"].add(r["TASK_ID"])
        signal_map[name]["alarms"] += r["alarm_count"] or 0
        signal_map[name]["samples"] += r["sample_count"] or 0
        if r["data_status"]:
            signal_map[name]["statuses"].add(r["data_status"])
        if r["updated_at"] and (not signal_map[name]["updated_at"] or r["updated_at"] > signal_map[name]["updated_at"]):
            signal_map[name]["updated_at"] = r["updated_at"]

    results = [
        SignalItem(
            signal_name=name, rule_ids=sorted(info["rule_ids"]), task_ids=sorted(info["task_ids"]),
            alarm_count=info["alarms"], sample_count=info["samples"],
            data_status="available" if "available" in info["statuses"] else "unavailable",
            updated_at=info["updated_at"],
        )
        for name, info in sorted(signal_map.items(), key=lambda pair: (-pair[1]["alarms"], pair[0]))
    ]

    # 按任务筛选
    if task_id is not None:
        results = [s for s in results if task_id in s.task_ids]
    # 按规则筛选
    if rule_id is not None:
        results = [s for s in results if rule_id in s.rule_ids]
    # 关键词搜索
    if keyword:
        kw = keyword.lower()
        results = [s for s in results if kw in s.signal_name.lower()]

    return results


@router.get("/{func_id}", response_model=FunctionResponse)
async def get_function(func_id: int):
    """获取单个函数"""
    func = get_freeze_function(func_id)
    if not func:
        raise HTTPException(status_code=404, detail="函数不存在")
    return func


@router.delete("/{func_id}")
async def delete_function(func_id: int):
    """软删除函数"""
    ok = soft_delete_freeze_function(func_id)
    if not ok:
        raise HTTPException(status_code=404, detail="函数不存在或已删除")
    return {"success": True, "message": "已删除"}


@router.post("/{func_id}/restore")
async def restore_function(func_id: int):
    """恢复被删除的函数"""
    ok = restore_freeze_function(func_id)
    if not ok:
        raise HTTPException(status_code=404, detail="函数不存在或未被删除")
    return {"success": True, "message": "已恢复"}
