"""明细宽表构建模块（WIDE_DETAIL）

用户设定的标准宽表结构：
  固定 12 字段：人员(person)、车型(vehicle_type)、车辆(vehicle)、
               任务(task)、规则名称(rule_name)、规则类型(rule_type)、
               表达式(expression)、前置条件满足时间(condition_met_time)、
               报警时间/前置条件不满足时间(alarm_time)、持续时间(duration_sec)、
               报警/统计数据(alarm_value)、冻结帧(freeze_frame)
  动态信号列：按 SIGNAL_NAME 出现频率 TOP-N 横向展开为独立列（来自实际数据）

构建策略：用 get_conn()（已有源库连接）执行数据查询，用 get_wide_conn()（宽表库）写入。
"""

from __future__ import annotations

import logging
import os
import time

import duckdb

try:
    from core.db_connector import get_conn, get_wide_db_path
except ImportError:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.db_connector import get_conn, get_wide_db_path

logger = logging.getLogger("db_initializer")

WIDE_DETAIL_TABLE = "WIDE_DETAIL"
LOG_TABLE = "_wide_detail_build_log"
TOP_SIGNALS_LIMIT = 200  # 默认 TOP-N 信号数
_SRC_CONN = None  # 源库连接（CLI 模式自己打开）


def _get_src_conn():
    """获取源库连接

    - API 模式（同进程）：复用 get_conn() 单例
    - CLI 模式（独立进程）：自己打开 read-only 连接
    """
    global _SRC_CONN
    if _SRC_CONN is not None:
        return _SRC_CONN
    # 先尝试复用服务端单例（API 模式）
    try:
        conn = get_conn()
        # 随便查一下，确认连接可用
        conn.execute("SELECT 1")
        _SRC_CONN = conn
        return _SRC_CONN
    except Exception:
        pass
    # 服务端未运行或锁冲突 → 自己打开 read-only 连接
    db_path = get_db_path()
    _SRC_CONN = duckdb.connect(db_path, read_only=True)
    _SRC_CONN.execute("SET threads TO 2;")
    _SRC_CONN.execute("SET memory_limit = '6GB';")
    _SRC_CONN.execute("SET preserve_insertion_order = false;")
    return _SRC_CONN

# ============================================================
# 固定 12 字段定义
# ============================================================

FIXED_COLUMNS: list[dict] = [
    {"name": "person",           "type": "VARCHAR"},
    {"name": "vehicle_type",     "type": "VARCHAR"},
    {"name": "vehicle",          "type": "VARCHAR"},
    {"name": "task",             "type": "VARCHAR"},
    {"name": "rule_name",        "type": "VARCHAR"},
    {"name": "rule_type",        "type": "VARCHAR"},
    {"name": "expression",       "type": "VARCHAR"},
    {"name": "condition_met_time","type": "TIMESTAMP"},
    {"name": "alarm_time",       "type": "TIMESTAMP"},
    {"name": "duration_sec",     "type": "DOUBLE"},
    {"name": "alarm_value",      "type": "VARCHAR"},
    {"name": "freeze_frame",     "type": "VARCHAR"},
]

RULE_TYPE_CASE = """
CASE r.RULE_TYPE
    WHEN 0 THEN '统计'
    WHEN 1 THEN '报警'
    WHEN 2 THEN '事件'
    ELSE ('未知(' || r.RULE_TYPE || ')')
END
""".strip()


def _compute_top_signal_names(src_conn, limit: int = TOP_SIGNALS_LIMIT) -> list[str]:
    """从源库信号表查询出现频率最高的 TOP-N 个信号名"""
    sql = f"""
    SELECT sig.SIGNAL_NAME
    FROM TL_RMU_PS_TASK_RULE_RESULT_SIGNAL sig
    WHERE sig.SIGNAL_NAME IS NOT NULL AND sig.SIGNAL_NAME <> ''
    GROUP BY sig.SIGNAL_NAME
    ORDER BY count(*) DESC
    LIMIT {int(limit)}
    """
    rows = src_conn.execute(sql).fetchall()
    return [r[0] for r in rows]


def _signal_col_type(signal_name: str) -> str:
    """信号列的 DuckDB 类型：转义双引号（如果含特殊字符）"""
    return f'"{signal_name.replace(chr(34), chr(34)*2)}" VARCHAR'


def _build_create_sql(signal_names: list[str]) -> str:
    """生成 WIDE_DETAIL 表的 CREATE TABLE DDL（不含数据）"""
    fixed_parts = [f'{c["name"]} {c["type"]}' for c in FIXED_COLUMNS]
    signal_parts = [_signal_col_type(s) for s in signal_names]
    all_cols = fixed_parts + signal_parts
    cols_sql = ",\n    ".join(all_cols)
    return (
        f"CREATE TABLE IF NOT EXISTS {WIDE_DETAIL_TABLE} (\n"
        f"    {cols_sql}\n"
        f")"
    )


def _build_data_sql(signal_names: list[str]) -> list[str]:
    """生成在源库连接上执行的 SQL 列表（多个步骤在一个 CTE 链中完成）

    返回 [with_cte_sql, final_select_sql]
    - with_cte_sql: 包含 base / signal_data / pivoted 的 WITH 语句
    - final_select_sql: 最终 SELECT 列
    """
    def esc(s: str) -> str:
        return s.replace("'", "''")

    # 基础 CTE — 源表无前缀（在源库连接上执行）
    base_cte = f"""
base AS (
    SELECT
        res.TASK_RULE_RESULT_ID                              AS _rid,
        coalesce(t.CREATE_BY, t.CREATE_BY_CODE, '')         AS person,
        coalesce(vtype.VEHICLETYPE_NAME, '')                 AS vehicle_type,
        coalesce(res.VIN, v.VIN, '')                         AS vehicle,
        t.TASK_NAME                                          AS task,
        r.RULE_NAME                                          AS rule_name,
        {RULE_TYPE_CASE}                                     AS rule_type,
        r.START_EXPRESSION_CONVERT                           AS expression,
        res.TRIGGER_TIME                                     AS condition_met_time,
        res.EXIT_TIME                                        AS alarm_time,
        (epoch(res.EXIT_TIME) -
         epoch(res.TRIGGER_TIME))::DOUBLE                    AS duration_sec,
        res.VALUE                                            AS alarm_value,
        res.FILE_NAME                                        AS freeze_frame
    FROM TL_RMU_PS_TASK_RULE_RESULT res
    LEFT JOIN TM_RMU_PS_TASK_RULE r       ON res.TASK_RULE_ID = r.TASK_RULE_ID
    LEFT JOIN TM_RMU_PS_TASK t            ON r.TASK_ID = t.TASK_ID
    LEFT JOIN TM_RMU_PS_TASK_VEHICLE v    ON res.VEHICLE_SID = v.VEHICLE_ID AND v.TASK_ID = t.TASK_ID
    LEFT JOIN TM_RMU_PS_TASK_VEHICLETYPE vtype ON v.TASK_VEHICLETYPE_ID = vtype.TASK_VEHICLETYPE_ID
    QUALIFY row_number() OVER (PARTITION BY res.TASK_RULE_RESULT_ID ORDER BY 1) = 1
)"""

    if not signal_names:
        with_cte = "WITH " + base_cte
        final_select = f"""
SELECT
    base.person,
    base.vehicle_type,
    base.vehicle,
    base.task,
    base.rule_name,
    base.rule_type,
    base.expression,
    base.condition_met_time,
    base.alarm_time,
    base.duration_sec,
    base.alarm_value,
    base.freeze_frame
FROM base
"""
        return [with_cte, final_select]

    # 有信号列 → PIVOT
    sig_in_list = ", ".join(f"'{esc(n)}'" for n in signal_names)
    sig_selects = [f'p."{esc(n)}"' for n in signal_names]

    with_cte = f"""
WITH {base_cte},
signal_data AS (
    SELECT
        sig.TASK_RULE_RESULT_ID AS _rid,
        sig.SIGNAL_NAME,
        sig.VALUE
    FROM TL_RMU_PS_TASK_RULE_RESULT_SIGNAL sig
    WHERE sig.SIGNAL_NAME IN ({sig_in_list})
),
pivoted AS (
    SELECT * FROM signal_data
    PIVOT (FIRST(VALUE) FOR SIGNAL_NAME IN ({sig_in_list}))
)
"""

    final_select = f"""
SELECT
    base.person,
    base.vehicle_type,
    base.vehicle,
    base.task,
    base.rule_name,
    base.rule_type,
    base.expression,
    base.condition_met_time,
    base.alarm_time,
    base.duration_sec,
    base.alarm_value,
    base.freeze_frame,
    {', '.join(sig_selects)}
FROM base
LEFT JOIN pivoted p ON base._rid = p._rid
"""

    return [with_cte, final_select]


def _index_sqls() -> list[str]:
    return [
        f'CREATE INDEX IF NOT EXISTS idx_wd_person              ON {WIDE_DETAIL_TABLE}("person");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_vehicle_type        ON {WIDE_DETAIL_TABLE}("vehicle_type");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_vehicle             ON {WIDE_DETAIL_TABLE}("vehicle");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_task                ON {WIDE_DETAIL_TABLE}("task");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_rule_name           ON {WIDE_DETAIL_TABLE}("rule_name");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_rule_type           ON {WIDE_DETAIL_TABLE}("rule_type");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_condition_met_time  ON {WIDE_DETAIL_TABLE}("condition_met_time");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_alarm_time          ON {WIDE_DETAIL_TABLE}("alarm_time");',
        f'CREATE INDEX IF NOT EXISTS idx_wd_duration_sec        ON {WIDE_DETAIL_TABLE}("duration_sec");',
    ]


def build_wide_table() -> bool:
    """执行明细宽表构建，成功返回 True

    流程：
    1. 用 get_conn()（源库）查询 TOP-N 信号名
    2. 在宽表库创建表结构（直接读写连接）
    3. 在源库上运行数据查询，用 Arrow 传输到宽表库写入
    """
    start = time.time()

    # ---- 1. 用源库连接查信号名 ----
    src_conn = _get_src_conn()
    signal_names = _compute_top_signal_names(src_conn, TOP_SIGNALS_LIMIT)
    logger.info("TOP-%d 信号列: %s (取前 10 项: %s)", TOP_SIGNALS_LIMIT,
                 len(signal_names), signal_names[:10])

    # ---- 2. 直接连接宽表库（读写），创建表 ----
    wide_conn = duckdb.connect(get_wide_db_path())
    wide_conn.execute("SET threads TO 2;")
    wide_conn.execute("SET memory_limit = '6GB';")
    wide_conn.execute("SET preserve_insertion_order = false;")
    wide_conn.execute(f"SET temp_directory = '{os.path.dirname(os.path.abspath(__file__))}/../duckdb_temp';")
    create_sql = _build_create_sql(signal_names)
    wide_conn.execute(f"DROP TABLE IF EXISTS {WIDE_DETAIL_TABLE}")
    wide_conn.execute(create_sql)
    logger.info("表 %s 已创建，字段数: %d", WIDE_DETAIL_TABLE,
                 len(FIXED_COLUMNS) + len(signal_names))

    # ---- 3. 在源库上执行数据查询，用 Arrow 在进程内传输到宽表库 ----
    with_cte_sql, final_select_sql = _build_data_sql(signal_names)
    full_sql = with_cte_sql + final_select_sql
    logger.info("开始执行数据查询（源库）...")
    # 在源库连接上执行查询，用 Arrow 表拿到全量结果（内存，无需锁）
    result = src_conn.execute(full_sql)
    arrow_tbl = result.to_arrow_table()
    logger.info("查询完成，Arrow 表行数: %s", f"{arrow_tbl.num_rows:,}")

    if arrow_tbl.num_rows > 0:
        # 在宽表库中注册 Arrow 表为临时视图，然后用 SQL 写入
        wide_conn.register("_wide_src", arrow_tbl)
        wide_conn.execute(f"INSERT INTO {WIDE_DETAIL_TABLE} SELECT * FROM _wide_src")
        wide_conn.unregister("_wide_src")
    logger.info("数据写入完成: %s 行, %.0f 秒", f"{arrow_tbl.num_rows:,}", time.time() - start)

    n_rows = arrow_tbl.num_rows

    # ---- 4. 创建索引 ----
    for s in _index_sqls():
        wide_conn.execute(s)
    logger.info("索引创建完成 (%d 个)", len(_index_sqls()))

    # ---- 5. 记录构建日志 ----
    cols_count = len(FIXED_COLUMNS) + len(signal_names)
    wide_conn.execute(f"CREATE TABLE IF NOT EXISTS {LOG_TABLE} "
                      "(build_time TIMESTAMP, row_count BIGINT, columns_count INT, signal_count INT)")
    wide_conn.execute(f"INSERT INTO {LOG_TABLE} VALUES (current_timestamp, {n_rows}, {cols_count}, {len(signal_names)})")

    logger.info("✅ WIDE_DETAIL 宽表就绪: %s 行 × %s 字段（固定12 + %d动态信号）",
                 f"{n_rows:,}", cols_count, len(signal_names))
    return True


def wide_detail_table_exists() -> bool:
    """检测 WIDE_DETAIL 表是否存在"""
    try:
        conn = get_wide_conn()
        result = conn.execute(
            f"SELECT count(*) FROM information_schema.tables "
            f"WHERE table_name = '{WIDE_DETAIL_TABLE}' AND table_schema = 'main'"
        ).fetchone()
        return result[0] > 0
    except Exception:
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    ok = build_wide_table()
    raise SystemExit(0 if ok else 1)
