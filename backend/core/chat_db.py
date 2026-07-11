"""聊天历史数据库（SQLite）

存储用户信息、对话会话、消息记录。
数据库文件：backend/data/ai_data.db
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import threading
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("chat_db")

if getattr(sys, "frozen", False):
    _backend_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = _backend_dir
DB_PATH = os.path.join(DATA_DIR, "ai_data.db")

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """获取线程本地连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=DELETE")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    """初始化数据库表结构"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS charts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            pivot_config TEXT NOT NULL,
            chart_type TEXT DEFAULT 'bar',
            data_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_charts_user ON charts(user_id);

        CREATE TABLE IF NOT EXISTS boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '默认看板',
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_boards_user ON boards(user_id);

        CREATE TABLE IF NOT EXISTS fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            alias_cn TEXT NOT NULL,
            data_type TEXT NOT NULL DEFAULT 'VARCHAR',
            description TEXT DEFAULT '',
            example_values TEXT,
            fixed INTEGER DEFAULT 0,
            category TEXT DEFAULT 'dimension',
            sort_order INTEGER DEFAULT 0
        );

        -- sqlite3.OperationalError 会被 execscript 吞掉，改用独立执行


        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT '新对话',
            mode TEXT DEFAULT 'chart',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            charts_json TEXT,
            suggestions_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user ON chat_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
    """)
    conn.commit()
    # Agent Trace 监控表（幂等创建）
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trace_spans (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            request_message TEXT NOT NULL,
            agent_name TEXT NOT NULL DEFAULT 'chart_agent',
            status TEXT NOT NULL DEFAULT 'in_progress',
            root_span_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_trace_session ON trace_spans(session_id);
        CREATE INDEX IF NOT EXISTS idx_trace_created ON trace_spans(created_at);
    """)
    # 幂等迁移：给 trace_spans 加 request_message 列（如果不存在）
    try:
        conn.execute("ALTER TABLE trace_spans ADD COLUMN request_message TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass
    seed_default_users()
    # 迁移：给 charts 加 board_id 列（幂等）
    try:
        conn.execute("ALTER TABLE charts ADD COLUMN board_id INTEGER REFERENCES boards(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_charts_board ON charts(board_id)")
    except Exception:
        pass  # 列已存在
    seed_default_boards()
    _init_external_data_tables()
    migrate_fields()
    logger.info("聊天历史数据库已初始化: %s", DB_PATH)


def seed_default_users():
    """首次初始化时创建默认用户"""
    conn = _get_conn()
    cur = conn.execute("SELECT count(*) FROM users")
    if cur.fetchone()[0] > 0:
        return
    for name in ["管理员", "分析员", "查看者"]:
        conn.execute("INSERT INTO users (username, role) VALUES (?, ?)", (name, "user"))
    conn.commit()
    logger.info("已创建 3 个默认用户: 管理员, 分析员, 查看者")


def seed_default_boards():
    """确保每个用户至少有一个默认看板（幂等）"""
    conn = _get_conn()
    users = list_all_users()
    now = datetime.now().isoformat()
    created = 0
    for u in users:
        cur = conn.execute("SELECT count(*) FROM boards WHERE user_id = ?", (u["id"],))
        if cur.fetchone()[0] > 0:
            continue
        conn.execute(
            "INSERT INTO boards (user_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (u["id"], "默认看板", "", now, now),
        )
        created += 1
    if created:
        conn.commit()
        logger.info("为 %d 个用户创建了默认看板", created)


def list_all_users() -> list[dict]:
    cur = _get_conn().execute("SELECT id, username, role FROM users ORDER BY id ASC")
    return [dict(r) for r in cur.fetchall()]



def seed_fields():
    """硬编码字段数据，导入到 fields 表（幂等）"""
    conn = _get_conn()
    cur = conn.execute("SELECT count(*) FROM fields")
    if cur.fetchone()[0] > 0:
        return

    FIELDS: list[tuple[str, str, str, str, int | None, str, int]] = [
        ("person", "人员", "VARCHAR", "", 1, "dimension", 0),
        ("vehicle_type", "车型", "VARCHAR", "", 1, "dimension", 1),
        ("vehicle", "车辆(VIN)", "VARCHAR", "", 1, "dimension", 2),
        ("task", "任务", "VARCHAR", "", 1, "dimension", 3),
        ("task_type", "任务类型", "VARCHAR", "", 1, "dimension", 4),
        ("task_status", "任务状态", "VARCHAR", "", 1, "dimension", 5),
        ("rule_name", "规则名称", "VARCHAR", "", 1, "dimension", 6),
        ("rule_type", "规则类型", "VARCHAR", "", 1, "dimension", 7),
        ("condition_met_time", "前置条件满足时间", "TIMESTAMP", "", 1, "time", 8),
        ("alarm_time", "报警时间/前置条件不满足时间", "TIMESTAMP", "", 1, "time", 9),
        ("duration_sec", "持续时间(秒)", "DOUBLE", "", 1, "measure", 10),
        ("create_time", "创建时间", "TIMESTAMP", "", 1, "measure", 11),
        ("trigger_time", "触发时间", "TIMESTAMP", "兼容外部透视查询请求的触发时间字段", 1, "time", 12),
    ]

    for name, alias_cn, data_type, description, fixed, category, sort_order in FIELDS:
        conn.execute(
            "INSERT INTO fields (name, alias_cn, data_type, description, example_values, fixed, category, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, alias_cn, data_type, description, None, fixed, category, sort_order),
        )
    conn.commit()
    logger.info("已硬编码导入 %d 个字段", len(FIELDS))


def clear_fields():
    """清除所有字段数据（用于迁移/重置）"""
    conn = _get_conn()
    conn.execute("DELETE FROM fields")
    conn.commit()
    logger.info("已清除所有字段数据")


def migrate_fields():
    """检测旧 的数据，替换为硬编码数据"""
    conn = _get_conn()
    cur = conn.execute("SELECT count(*) FROM fields")
    count = cur.fetchone()[0]
    if count == 0:
        seed_fields()
        return
    # 检查是否包含 trigger_time（新硬编码数据的标志）
    has_trigger = conn.execute("SELECT count(*) FROM fields WHERE name = 'trigger_time'").fetchone()[0] > 0
    if has_trigger:
        logger.info("字段已是硬编码数据，跳过迁移")
        return
    # 旧数据存在，清除后重新导入
    logger.info("检测到旧字段数据（%d 条），开始迁移为硬编码数据...", count)
    conn.execute("DELETE FROM fields")
    seed_fields()


def list_fields() -> list[dict]:
    """获取所有字段列表"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, name, alias_cn, data_type, description, example_values, fixed, category FROM fields ORDER BY sort_order ASC, id ASC"
    )
    result = []
    for r in cur.fetchall():
        item = dict(r)
        item["fixed"] = bool(item["fixed"])
        result.append(item)
    return result


def get_field_names() -> list[str]:
    """获取所有字段名"""
    conn = _get_conn()
    cur = conn.execute("SELECT name FROM fields ORDER BY sort_order ASC, id ASC")
    return [r[0] for r in cur.fetchall()]


def get_fixed_field_names() -> set[str]:
    """获取所有固定字段名"""
    conn = _get_conn()
    cur = conn.execute("SELECT name FROM fields WHERE fixed = 1")
    return {r[0] for r in cur.fetchall()}
def get_or_create_user(username: str) -> dict:
    """按用户名查找，不存在则创建"""
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if row:
        return dict(row)
    cur = conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
    conn.commit()
    return {"id": cur.lastrowid, "username": username, "role": "user"}


# ====== 用户操作 ======

def get_or_create_user(username: str) -> dict:
    """按用户名查找或创建用户"""
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if row:
        return dict(row)
    cur = conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
    conn.commit()
    return {"id": cur.lastrowid, "username": username, "role": "user"}


def get_user(user_id: int) -> Optional[dict]:
    cur = _get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    return dict(row) if row else None


# ====== 会话操作 ======

def list_sessions(user_id: int) -> list[dict]:
    cur = _get_conn().execute(
        "SELECT id, user_id, title, mode, created_at, updated_at "
        "FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def get_session(session_id: str) -> Optional[dict]:
    cur = _get_conn().execute(
        "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
    )
    row = cur.fetchone()
    return dict(row) if row else None


def create_session(session_id: str, user_id: int, title: str = "新对话", mode: str = "chart") -> dict:
    now = datetime.now().isoformat()
    _get_conn().execute(
        "INSERT INTO chat_sessions (id, user_id, title, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, user_id, title, mode, now, now),
    )
    _get_conn().commit()
    return {"id": session_id, "user_id": user_id, "title": title, "mode": mode}


def update_session_title(session_id: str, title: str):
    _get_conn().execute(
        "UPDATE chat_sessions SET title = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (title, session_id),
    )
    _get_conn().commit()


def update_session_mode(session_id: str, mode: str):
    _get_conn().execute(
        "UPDATE chat_sessions SET mode = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (mode, session_id),
    )
    _get_conn().commit()


def delete_session(session_id: str):
    conn = _get_conn()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()


# ====== 消息操作 ======

def get_messages(session_id: str) -> list[dict]:
    cur = _get_conn().execute(
        "SELECT id, session_id, role, content, charts_json, suggestions_json, created_at "
        "FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    )
    result = []
    for r in cur.fetchall():
        msg = dict(r)
        if msg["charts_json"]:
            try:
                msg["charts"] = json.loads(msg["charts_json"])
            except json.JSONDecodeError:
                msg["charts"] = []
        else:
            msg["charts"] = []
        if msg["suggestions_json"]:
            try:
                msg["suggestions"] = json.loads(msg["suggestions_json"])
            except json.JSONDecodeError:
                msg["suggestions"] = []
        else:
            msg["suggestions"] = []
        del msg["charts_json"]
        del msg["suggestions_json"]
        result.append(msg)
    return result


def add_message(session_id: str, role: str, content: str, charts: list = None, suggestions: list = None):
    charts_json = json.dumps(charts, ensure_ascii=False) if charts else None
    suggestions_json = json.dumps(suggestions, ensure_ascii=False) if suggestions else None
    conn = _get_conn()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, charts_json, suggestions_json) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, charts_json, suggestions_json),
    )
    conn.execute(
        "UPDATE chat_sessions SET updated_at = datetime('now','localtime') WHERE id = ?",
        (session_id,),
    )
    conn.commit()


# ====== 看板操作 ======

def list_boards(user_id: int) -> list[dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, user_id, name, description, created_at, updated_at "
        "FROM boards WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def get_board(board_id: int) -> dict | None:
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM boards WHERE id = ?", (board_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def create_board(user_id: int, name: str, description: str = "") -> dict:
    conn = _get_conn()
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO boards (user_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, description, now, now),
    )
    conn.commit()
    return {"id": cur.lastrowid, "user_id": user_id, "name": name, "description": description,
            "created_at": now, "updated_at": now}


def update_board(board_id: int, name: str = None, description: str = None) -> dict | None:
    conn = _get_conn()
    existing = get_board(board_id)
    if not existing:
        return None
    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if fields:
        fields.append("updated_at = datetime('now','localtime')")
        params.append(board_id)
        conn.execute(f"UPDATE boards SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    return get_board(board_id)


def delete_board(board_id: int) -> bool:
    conn = _get_conn()
    conn.execute("DELETE FROM charts WHERE board_id = ?", (board_id,))
    cur = conn.execute("DELETE FROM boards WHERE id = ?", (board_id,))
    conn.commit()
    return cur.rowcount > 0


# ====== 看板图表操作 ======

def list_charts(board_id: int) -> list[dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, user_id, title, description, pivot_config, chart_type, data_json, created_at, updated_at "
        "FROM charts WHERE board_id = ? ORDER BY updated_at DESC", (board_id,))
    result = []
    for r in cur.fetchall():
        item = dict(r)
        if item["pivot_config"]:
            try:
                item["pivot_config"] = json.loads(item["pivot_config"])
            except json.JSONDecodeError:
                item["pivot_config"] = {}
        if item["data_json"]:
            try:
                item["data"] = json.loads(item["data_json"])
            except json.JSONDecodeError:
                item["data"] = []
        else:
            item["data"] = []
        del item["data_json"]
        result.append(item)
    return result


def get_chart(chart_id: int) -> dict | None:
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM charts WHERE id = ?", (chart_id,))
    row = cur.fetchone()
    if not row:
        return None
    item = dict(row)
    if item["pivot_config"]:
        try:
            item["pivot_config"] = json.loads(item["pivot_config"])
        except json.JSONDecodeError:
            item["pivot_config"] = {}
    if item["data_json"]:
        try:
            item["data"] = json.loads(item["data_json"])
        except json.JSONDecodeError:
            item["data"] = []
    else:
        item["data"] = []
    del item["data_json"]
    return item


def create_chart(user_id: int, title: str, pivot_config: dict, chart_type: str = "bar",
                 description: str = "", data: list = None, board_id: int = None) -> dict:
    conn = _get_conn()
    pivot_json = json.dumps(pivot_config, ensure_ascii=False)
    data_json = json.dumps(data, ensure_ascii=False) if data else None
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO charts (user_id, title, description, pivot_config, chart_type, data_json, board_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, title, description, pivot_json, chart_type, data_json, board_id, now, now),
    )
    conn.commit()
    return {"id": cur.lastrowid, "user_id": user_id, "title": title, "description": description,
            "pivot_config": pivot_config, "chart_type": chart_type, "data": data or [],
            "created_at": now, "updated_at": now}


def update_chart(chart_id: int, title: str = None, description: str = None,
                 pivot_config: dict = None, chart_type: str = None, data: list = None) -> dict | None:
    conn = _get_conn()
    existing = get_chart(chart_id)
    if not existing:
        return None
    fields = []
    params = []
    if title is not None:
        fields.append("title = ?")
        params.append(title)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if pivot_config is not None:
        fields.append("pivot_config = ?")
        params.append(json.dumps(pivot_config, ensure_ascii=False))
    if chart_type is not None:
        fields.append("chart_type = ?")
        params.append(chart_type)
    if data is not None:
        fields.append("data_json = ?")
        params.append(json.dumps(data, ensure_ascii=False))
    if fields:
        fields.append("updated_at = datetime('now','localtime')")
        params.append(chart_id)
        conn.execute(f"UPDATE charts SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    return get_chart(chart_id)


def delete_chart(chart_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM charts WHERE id = ?", (chart_id,))
    conn.commit()
    return cur.rowcount > 0


def init_default_user() -> dict:
    """初始化默认用户（用于首次启动时自动创建）"""
    return get_or_create_user("default_user")


# ====== Agent Trace 监控 ======

def create_trace_span(
    trace_id: str,
    session_id: str,
    request_message: str,
    agent_name: str = "chart_agent",
) -> dict:
    """创建一条新的 Agent trace 记录"""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO trace_spans (id, session_id, request_message, agent_name, status, root_span_json) "
        "VALUES (?, ?, ?, ?, 'in_progress', '{}')",
        (trace_id, session_id, request_message, agent_name),
    )
    conn.commit()
    return {
        "id": trace_id,
        "session_id": session_id,
        "request_message": request_message,
        "agent_name": agent_name,
        "status": "in_progress",
        "root_span_json": "{}",
    }


def update_trace_status(
    trace_id: str,
    status: str,
    root_span_json: str,
) -> bool:
    """更新 trace 状态和完整 span 树"""
    logger.debug("update_trace_status: id=%s status=%s root_json_len=%s", trace_id, status, len(root_span_json))
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE trace_spans SET status = ?, root_span_json = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (status, root_span_json, trace_id),
    )
    conn.commit()
    affected = cur.rowcount > 0
    logger.debug("update_trace_status: affected=%s", affected)
    return affected


def list_trace_summaries(limit: int = 50, offset: int = 0, session_id: str | None = None) -> list[dict]:
    """列出 trace 摘要列表（不含 root_span_json）"""
    conn = _get_conn()
    if session_id:
        cur = conn.execute(
            "SELECT id, session_id, request_message, agent_name, status, created_at, updated_at "
            "FROM trace_spans WHERE session_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        )
    else:
        cur = conn.execute(
            "SELECT id, session_id, request_message, agent_name, status, created_at, updated_at "
            "FROM trace_spans ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    return [dict(r) for r in cur.fetchall()]


def get_trace_detail(trace_id: str) -> dict | None:
    """获取完整 trace 详情（含 root_span_json）"""
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM trace_spans WHERE id = ?", (trace_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def list_session_ids_for_traces(limit: int = 100) -> list[dict]:
    """获取所有有 trace 记录的会话 ID 列表"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT DISTINCT session_id, MAX(created_at) as last_trace "
        "FROM trace_spans GROUP BY session_id ORDER BY last_trace DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in cur.fetchall()]


def get_trace_stats() -> dict:
    """获取 trace 统计信息"""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM trace_spans").fetchone()[0]
    success = conn.execute("SELECT COUNT(*) FROM trace_spans WHERE status = 'success'").fetchone()[0]
    error = conn.execute("SELECT COUNT(*) FROM trace_spans WHERE status = 'error'").fetchone()[0]
    return {
        "total": total,
        "success": success,
        "error": error,
    }


# ============================================================
# 外部数据（任务/规则/车辆）—— 从 DuckDB 同步的维表
# ============================================================

_EXT_DATA_INITIALIZED = False

def _init_external_data_tables():
    """初始化外部数据维表（幂等），首次时从 seed SQL 导入"""
    global _EXT_DATA_INITIALIZED
    if _EXT_DATA_INITIALIZED:
        return
    conn = _get_conn()
    
    # 建表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ext_tasks (
            TASK_ID INTEGER PRIMARY KEY,
            TASK_NAME TEXT,
            TASK_TYPE INTEGER,
            TASK_PRIORITY INTEGER,
            TASK_DB_MODE INTEGER,
            TASK_START_TIME TEXT,
            TASK_END_TIME TEXT,
            TASK_EXECUTE_START_TIME TEXT,
            TASK_EXECUTE_END_TIME TEXT,
            ANALYSIS_STATE INTEGER,
            RMUDATA_STATE INTEGER,
            MERGE_STATE INTEGER,
            APPROVE_STATE INTEGER,
            APPROVE_REMARK TEXT,
            IS_DELETE INTEGER,
            CREATE_BY TEXT,
            CREATE_TIME TEXT,
            UPDATE_BY TEXT,
            UPDATE_TIME TEXT,
            EXTRA1 INTEGER,
            EXTRA2 TEXT,
            EXTRA3 TEXT,
            VESCOM_ID INTEGER,
            IS_PUBLIC INTEGER DEFAULT 0,
            CREATE_BY_CODE TEXT,
            UPDATE_BY_CODE TEXT,
            REPORT_ID INTEGER,
            IS_NOTICE INTEGER,
            WARNING_TIMES INTEGER,
            CYCLE REAL,
            UNIT TEXT,
            WARNING_TIME TEXT,
            DATASOURCE INTEGER
        );

        CREATE TABLE IF NOT EXISTS ext_rules (
            TASK_RULE_ID INTEGER PRIMARY KEY,
            TASK_ID INTEGER,
            RULE_NAME TEXT,
            RULE_DESCRIPTION TEXT,
            RULE_MODE INTEGER,
            START_EXPRESSION TEXT,
            START_EXPRESSION_CONVERT TEXT,
            START_EXPRESSION_ID INTEGER,
            START_EXPRESSION_PARAM TEXT,
            END_EXPRESSION TEXT,
            END_EXPRESSION_CONVERT TEXT,
            END_EXPRESSION_ID INTEGER,
            END_EXPRESSION_PARAM TEXT,
            JUDGE_EXPRESSION TEXT,
            JUDGE_EXPRESSION_CONVERT TEXT,
            JUDGE_EXPRESSION_ID INTEGER,
            JUDGE_EXPRESSION_PARAM TEXT,
            RULE_TYPE INTEGER,
            RULE_END_TIME TEXT,
            RBF_BEFORE_TIME REAL,
            RBF_AFTER_TIME REAL,
            RULE_SIGNALS TEXT,
            OTHER_SIGNALS TEXT
        );

        CREATE TABLE IF NOT EXISTS ext_vehicles (
            TASK_VEHICLE_ID INTEGER PRIMARY KEY,
            TASK_VEHICLETYPE_ID INTEGER,
            VEHICLE_ID INTEGER,
            TASK_ID INTEGER,
            VIN TEXT,
            VIN_PATAC_ID TEXT,
            RMU_CODE TEXT,
            STATE INTEGER DEFAULT 0,
            EXTRA1 INTEGER,
            EXTRA2 TEXT,
            EXTRA3 TEXT,
            IS_DEL INTEGER DEFAULT 0,
            UPDATE_TIME TEXT
        );

        CREATE TABLE IF NOT EXISTS ext_vehicle_types (
            TASK_VEHICLETYPE_ID INTEGER PRIMARY KEY,
            TASK_ID INTEGER,
            VEHICLETYPE_NAME TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ext_tasks_name ON ext_tasks(TASK_NAME);
        CREATE INDEX IF NOT EXISTS idx_ext_rules_task ON ext_rules(TASK_ID);
        CREATE INDEX IF NOT EXISTS idx_ext_rules_name ON ext_rules(RULE_NAME);
        CREATE INDEX IF NOT EXISTS idx_ext_vehicles_task ON ext_vehicles(TASK_ID);
        CREATE INDEX IF NOT EXISTS idx_ext_vehicle_types_task ON ext_vehicle_types(TASK_ID);
    """)

    # 判断是否需要导入 seed 数据
    cur = conn.execute("SELECT COUNT(*) FROM ext_tasks")
    if cur.fetchone()[0] > 0:
        _EXT_DATA_INITIALIZED = True
        logger.info("外部数据维表已存在，跳过 seed 导入")
        return

    # 导入 CSV 数据
    _ext_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ext_data_csv")
    _ext_path = os.path.abspath(_ext_dir)
    if os.path.isdir(_ext_path):
        try:
            import csv
            csv_files = [
                ("ext_tasks", "TM_RMU_PS_TASK.csv"),
                ("ext_rules", "TM_RMU_PS_TASK_RULE.csv"),
                ("ext_vehicles", "TM_RMU_PS_TASK_VEHICLE.csv"),
                ("ext_vehicle_types", "TM_RMU_PS_TASK_VEHICLETYPE.csv"),
            ]
            for table_name, csv_file in csv_files:
                csv_path = os.path.join(_ext_path, csv_file)
                if not os.path.exists(csv_path):
                    logger.warning("CSV 文件不存在: %s", csv_path)
                    continue
                with open(csv_path, "r", encoding="utf-8") as fh:
                    reader = csv.reader(fh)
                    headers = next(reader)
                    placeholders = ",".join(["?" for _ in headers])
                    col_names = ",".join(headers)
                    rows = list(reader)
                    conn.executemany(
                        f"INSERT OR IGNORE INTO {table_name} ({col_names}) VALUES ({placeholders})",
                        rows,
                    )
                logger.info("  已导入 %s -> %s (%d rows)", csv_file, table_name, len(rows))
            conn.commit()
            _EXT_DATA_INITIALIZED = True
            logger.info("已从 ext_data_csv/ 导入外部数据维表")
        except Exception as e:
            logger.error("导入外部数据失败: %s", e)
            import traceback
            traceback.print_exc()
    else:
        logger.warning("ext_data_csv/ 目录不存在，跳过外部数据导入")


# ============================================================
# 外部数据 CRUD（供 Agent 使用）
# ============================================================

def search_tasks(query: str = "", limit: int = 20) -> list[dict]:
    """搜索任务（按名称模糊匹配）"""
    conn = _get_conn()
    if query:
        cur = conn.execute(
            "SELECT * FROM ext_tasks WHERE TASK_NAME LIKE ? AND (IS_DELETE IS NULL OR IS_DELETE = 0) ORDER BY TASK_ID LIMIT ?",
            (f"%{query}%", limit),
        )
    else:
        cur = conn.execute(
            "SELECT * FROM ext_tasks WHERE (IS_DELETE IS NULL OR IS_DELETE = 0) ORDER BY TASK_ID LIMIT ?",
            (limit,),
        )
    return [dict(r) for r in cur.fetchall()]


def search_rules(query: str = "", task_id: int | None = None, limit: int = 20) -> list[dict]:
    """搜索规则（按名称/描述模糊匹配，可按任务筛选）"""
    conn = _get_conn()
    if task_id:
        if query:
            cur = conn.execute(
                "SELECT * FROM ext_rules WHERE TASK_ID = ? AND (RULE_NAME LIKE ? OR RULE_DESCRIPTION LIKE ?) ORDER BY TASK_RULE_ID LIMIT ?",
                (task_id, f"%{query}%", f"%{query}%", limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM ext_rules WHERE TASK_ID = ? ORDER BY TASK_RULE_ID LIMIT ?",
                (task_id, limit),
            )
    else:
        if query:
            cur = conn.execute(
                "SELECT * FROM ext_rules WHERE RULE_NAME LIKE ? OR RULE_DESCRIPTION LIKE ? ORDER BY TASK_RULE_ID LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM ext_rules ORDER BY TASK_RULE_ID LIMIT ?",
                (limit,),
            )
    return [dict(r) for r in cur.fetchall()]


def list_task_rules(task_id: int) -> list[dict]:
    """获取指定任务下的所有规则"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM ext_rules WHERE TASK_ID = ? ORDER BY TASK_RULE_ID",
        (task_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def get_task(task_id: int) -> dict | None:
    """获取单个任务"""
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM ext_tasks WHERE TASK_ID = ?", (task_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_rule(rule_id: int) -> dict | None:
    """获取单个规则"""
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM ext_rules WHERE TASK_RULE_ID = ?", (rule_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def list_vehicles_for_task(task_id: int) -> list[dict]:
    """获取指定任务下的车辆列表"""
    conn = _get_conn()
    sql = "SELECT v.*, vt.VEHICLETYPE_NAME FROM ext_vehicles v " \
          "LEFT JOIN ext_vehicle_types vt ON v.TASK_VEHICLETYPE_ID = vt.TASK_VEHICLETYPE_ID " \
          "WHERE v.TASK_ID = ? ORDER BY v.TASK_VEHICLE_ID LIMIT 100"
    cur = conn.execute(sql, (task_id,))
    return [dict(r) for r in cur.fetchall()]


def list_all_tasks(limit: int = 100) -> list[dict]:
    """列出所有任务"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM ext_tasks WHERE (IS_DELETE IS NULL OR IS_DELETE = 0) ORDER BY TASK_ID LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in cur.fetchall()]


def list_all_rules(limit: int = 100) -> list[dict]:
    """列出所有规则"""
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM ext_rules ORDER BY TASK_RULE_ID LIMIT ?", (limit,))
    return [dict(r) for r in cur.fetchall()]
