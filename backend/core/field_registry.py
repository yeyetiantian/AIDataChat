"""大宽表字段注册表

所有 104 个字段的定义，含中文别名、数据类型、所属源表、业务说明。
用于：
1. 前端字段列表展示
2. LangGraph Agent 的 Schema 注入
3. 大宽表构建时的列定义
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class FieldDef(BaseModel):
    """字段定义"""
    name: str = Field(..., description="字段名（大宽表中的列名）")
    alias_cn: str = Field(..., description="中文别名")
    data_type: str = Field(..., description="数据类型")
    source_table: str = Field(..., description="源表名")
    description: str = Field("", description="业务说明")
    category: Literal["id", "dimension", "measure", "time", "status", "file", "ext"] = Field(
        "dimension", description="字段分类"
    )
    example_values: Optional[str] = Field(None, description="示例值")
    in_wide_table: bool = Field(True, description="是否在大宽表中可用")


# ============================================================
# 全部字段注册表（104 个字段，按源表分组）
# ============================================================

_FIELDS: list[FieldDef] = [
    # ---- TM_RMU_PS_TASK（33 个字段） ----
    FieldDef(name="TASK_ID", alias_cn="任务 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="id"),
    FieldDef(name="TASK_NAME", alias_cn="任务名称", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="TASK_TYPE", alias_cn="任务类型", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="TASK_PRIORITY", alias_cn="任务优先级", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="TASK_DB_MODE", alias_cn="数据库模式", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="TASK_START_TIME", alias_cn="任务开始时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK", category="time"),
    FieldDef(name="TASK_END_TIME", alias_cn="任务结束时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK", category="time"),
    FieldDef(name="TASK_EXECUTE_START_TIME", alias_cn="任务执行开始时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK", category="time"),
    FieldDef(name="TASK_EXECUTE_END_TIME", alias_cn="任务执行结束时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK", category="time"),
    FieldDef(name="ANALYSIS_STATE", alias_cn="分析状态", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="status"),
    FieldDef(name="RMUDATA_STATE", alias_cn="RMU 数据状态", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="status"),
    FieldDef(name="MERGE_STATE", alias_cn="合并状态", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="status"),
    FieldDef(name="APPROVE_STATE", alias_cn="审批状态", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="status"),
    FieldDef(name="APPROVE_REMARK", alias_cn="审批备注", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="IS_DELETE", alias_cn="是否删除", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="status"),
    FieldDef(name="CREATE_BY", alias_cn="创建人", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="CREATE_TIME", alias_cn="创建时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK", category="time"),
    FieldDef(name="UPDATE_BY", alias_cn="更新人", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="UPDATE_TIME", alias_cn="更新时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK", category="time"),
    FieldDef(name="EXTRA1", alias_cn="扩展字段 1", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="ext"),
    FieldDef(name="EXTRA2", alias_cn="扩展字段 2", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="ext"),
    FieldDef(name="EXTRA3", alias_cn="扩展字段 3", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="ext"),
    FieldDef(name="VESCOM_ID", alias_cn="VESCOM ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="id"),
    FieldDef(name="IS_PUBLIC", alias_cn="是否公开", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="status"),
    FieldDef(name="CREATE_BY_CODE", alias_cn="创建人工号", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="UPDATE_BY_CODE", alias_cn="更新人工号", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="REPORT_ID", alias_cn="报表 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="id"),
    FieldDef(name="IS_NOTICE", alias_cn="是否通知", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="status"),
    FieldDef(name="WARNING_TIMES", alias_cn="告警次数", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="measure"),
    FieldDef(name="CYCLE", alias_cn="周期", data_type="DECIMAL(8,2)", source_table="TM_RMU_PS_TASK", category="measure"),
    FieldDef(name="UNIT", alias_cn="单位", data_type="VARCHAR", source_table="TM_RMU_PS_TASK", category="dimension"),
    FieldDef(name="WARNING_TIME", alias_cn="告警时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK", category="time"),
    FieldDef(name="DATASOURCE", alias_cn="数据源", data_type="INTEGER", source_table="TM_RMU_PS_TASK", category="dimension"),

    # ---- TM_RMU_PS_TASK_RULE（23 个字段） ----
    FieldDef(name="RULE_TASK_RULE_ID", alias_cn="规则 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_RULE", category="id"),
    FieldDef(name="RULE_TASK_ID", alias_cn="规则所属任务 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_RULE", category="id"),
    FieldDef(name="RULE_NAME", alias_cn="规则名称", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="RULE_DESCRIPTION", alias_cn="规则描述", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="RULE_MODE", alias_cn="规则模式", data_type="INTEGER", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="START_EXPRESSION", alias_cn="开始表达式", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="START_EXPRESSION_CONVERT", alias_cn="开始表达式（转换后）", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="START_EXPRESSION_ID", alias_cn="开始表达式 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_RULE", category="id"),
    FieldDef(name="START_EXPRESSION_PARAM", alias_cn="开始表达式参数", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="END_EXPRESSION", alias_cn="结束表达式", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="END_EXPRESSION_CONVERT", alias_cn="结束表达式（转换后）", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="END_EXPRESSION_ID", alias_cn="结束表达式 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_RULE", category="id"),
    FieldDef(name="END_EXPRESSION_PARAM", alias_cn="结束表达式参数", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="JUDGE_EXPRESSION", alias_cn="判定表达式", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="JUDGE_EXPRESSION_CONVERT", alias_cn="判定表达式（转换后）", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="JUDGE_EXPRESSION_ID", alias_cn="判定表达式 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_RULE", category="id"),
    FieldDef(name="JUDGE_EXPRESSION_PARAM", alias_cn="判定表达式参数", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="RULE_TYPE", alias_cn="规则类型", data_type="INTEGER", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="RULE_END_TIME", alias_cn="规则结束时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK_RULE", category="time"),
    FieldDef(name="RBF_BEFORE_TIME", alias_cn="RBF 截取前时间", data_type="DECIMAL(18,3)", source_table="TM_RMU_PS_TASK_RULE", category="measure"),
    FieldDef(name="RBF_AFTER_TIME", alias_cn="RBF 截取后时间", data_type="DECIMAL(18,3)", source_table="TM_RMU_PS_TASK_RULE", category="measure"),
    FieldDef(name="RULE_SIGNALS", alias_cn="规则关联信号", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),
    FieldDef(name="OTHER_SIGNALS", alias_cn="其他信号", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_RULE", category="dimension"),

    # ---- TL_RMU_PS_TASK_RULE_RESULT（24 个字段） ----
    FieldDef(name="TASK_RULE_RESULT_ID", alias_cn="结果 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),
    FieldDef(name="TASK_RULE_ID", alias_cn="结果关联规则 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),
    FieldDef(name="VEHICLE_SID", alias_cn="车辆 SID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),
    FieldDef(name="VIN", alias_cn="车架号", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="dimension", example_values="LSGTC54M75Y123456"),
    FieldDef(name="RMU_CODE", alias_cn="RMU 编码", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="dimension"),
    FieldDef(name="FILE_NAME", alias_cn="文件名", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="dimension"),
    FieldDef(name="TIME", alias_cn="日期", data_type="DATE", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="time"),
    FieldDef(name="RESULT_VALUE", alias_cn="结果值", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="measure"),
    FieldDef(name="RMU_FILE_STATE", alias_cn="RMU 文件状态", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="status"),
    FieldDef(name="RBF_FILE_ID", alias_cn="RBF 文件 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),
    FieldDef(name="RBF_STATE", alias_cn="RBF 状态", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="status"),
    FieldDef(name="RBF_REMARK", alias_cn="RBF 备注", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="dimension"),
    FieldDef(name="MF4_FILE_ID", alias_cn="MF4 文件 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),
    FieldDef(name="MF4_STATE", alias_cn="MF4 状态", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="status"),
    FieldDef(name="MF4_REMARK", alias_cn="MF4 备注", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="dimension"),
    FieldDef(name="VSB_FILE_ID", alias_cn="VSB 文件 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),
    FieldDef(name="VSB_STATE", alias_cn="VSB 状态", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="status"),
    FieldDef(name="VSB_REMARK", alias_cn="VSB 备注", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="dimension"),
    FieldDef(name="ASC_FILE_ID", alias_cn="ASC 文件 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),
    FieldDef(name="ASC_STATE", alias_cn="ASC 状态", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="status"),
    FieldDef(name="ASC_REMARK", alias_cn="ASC 备注", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="dimension"),
    FieldDef(name="EXIT_TIME", alias_cn="退出时间", data_type="TIMESTAMP", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="time"),
    FieldDef(name="TRIGGER_TIME", alias_cn="触发时间", data_type="TIMESTAMP", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="time"),
    FieldDef(name="MASTER_ID", alias_cn="主 ID", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT", category="id"),

    # ---- TM_RMU_PS_TASK_VEHICLE（13 个字段） ----
    FieldDef(name="TVEHICLE_TASK_VEHICLE_ID", alias_cn="任务车辆 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLE", category="id"),
    FieldDef(name="TVEHICLE_TASK_VEHICLETYPE_ID", alias_cn="任务车型 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLE", category="id"),
    FieldDef(name="TVEHICLE_VEHICLE_ID", alias_cn="车辆 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLE", category="id"),
    FieldDef(name="TVEHICLE_TASK_ID", alias_cn="车辆关联任务 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLE", category="id"),
    FieldDef(name="TVEHICLE_VIN", alias_cn="车辆车架号", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_VEHICLE", category="dimension"),
    FieldDef(name="VIN_PATAC_ID", alias_cn="VIN PATAC ID", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_VEHICLE", category="id"),
    FieldDef(name="TVEHICLE_RMU_CODE", alias_cn="车辆 RMU 编码", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_VEHICLE", category="dimension"),
    FieldDef(name="VEHICLE_STATE", alias_cn="车辆状态", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLE", category="status"),
    FieldDef(name="TVEHICLE_EXTRA1", alias_cn="车辆扩展字段 1", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLE", category="ext"),
    FieldDef(name="TVEHICLE_EXTRA2", alias_cn="车辆扩展字段 2", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_VEHICLE", category="ext"),
    FieldDef(name="TVEHICLE_EXTRA3", alias_cn="车辆扩展字段 3", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_VEHICLE", category="ext"),
    FieldDef(name="IS_DEL", alias_cn="是否删除（车辆）", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLE", category="status"),
    FieldDef(name="TVEHICLE_UPDATE_TIME", alias_cn="车辆更新时间", data_type="TIMESTAMP", source_table="TM_RMU_PS_TASK_VEHICLE", category="time"),

    # ---- TM_RMU_PS_TASK_VEHICLETYPE（3 个字段） ----
    FieldDef(name="VTYPE_TASK_VEHICLETYPE_ID", alias_cn="车型 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLETYPE", category="id"),
    FieldDef(name="VTYPE_TASK_ID", alias_cn="车型关联任务 ID", data_type="INTEGER", source_table="TM_RMU_PS_TASK_VEHICLETYPE", category="id"),
    FieldDef(name="VEHICLETYPE_NAME", alias_cn="车型名称", data_type="VARCHAR", source_table="TM_RMU_PS_TASK_VEHICLETYPE", category="dimension", example_values="SUV, MPV, 轿车, 新能源"),

    # ---- TL_RMU_PS_TASK_RULE_RESULT_SIGNAL（8 个字段） ----
    FieldDef(name="RULE_RESULT_SIGNAL_ID", alias_cn="信号 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="id", in_wide_table=True),
    FieldDef(name="SIGNAL_TASK_RULE_RESULT_ID", alias_cn="信号关联结果 ID", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="id", in_wide_table=True),
    FieldDef(name="SIGNAL_TYPE", alias_cn="信号类型", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="dimension", in_wide_table=True),
    FieldDef(name="SIGNAL_NAME", alias_cn="信号名称", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="dimension", example_values="车速, 发动机转速, 油门开度", in_wide_table=True),
    FieldDef(name="SIGNAL_VALUE", alias_cn="信号值", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="measure", in_wide_table=True),
    FieldDef(name="SIGNAL_EXTRA_1", alias_cn="信号扩展字段 1", data_type="BIGINT", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="ext", in_wide_table=True),
    FieldDef(name="SIGNAL_EXTRA_2", alias_cn="信号扩展字段 2", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="ext", in_wide_table=True),
    FieldDef(name="SIGNAL_EXTRA_3", alias_cn="信号扩展字段 3", data_type="VARCHAR", source_table="TL_RMU_PS_TASK_RULE_RESULT_SIGNAL", category="ext", in_wide_table=True),
]


# ============================================================
# 明细宽表 (WIDE_DETAIL)：8 个固定业务字段 + 动态信号名列
# ============================================================

# 固定字段的字段定义（宽表中列名，与 detail_builder.py 一致）
WIDE_DETAIL_TABLE = "WIDE_DETAIL"
WIDE_DETAIL_TABLE_CN = "明细宽表"
WIDE_DETAIL_FIXED_FIELDS: list[FieldDef] = [
    FieldDef(name="person",           alias_cn="人员",                     data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="vehicle_type",     alias_cn="车型",                     data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="vehicle",          alias_cn="车辆(VIN)",               data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="task",             alias_cn="任务",                     data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="rule_name",        alias_cn="规则名称",                 data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="rule_type",        alias_cn="规则类型",                 data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),  # 报警/统计/事件
    FieldDef(name="expression",       alias_cn="表达式",                   data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
    FieldDef(name="condition_met_time", alias_cn="前置条件满足时间",        data_type="TIMESTAMP", source_table=WIDE_DETAIL_TABLE, category="time"),
    FieldDef(name="alarm_time",       alias_cn="报警时间/前置条件不满足时间", data_type="TIMESTAMP", source_table=WIDE_DETAIL_TABLE, category="time"),
    FieldDef(name="duration_sec",     alias_cn="持续时间(秒)",             data_type="DOUBLE",    source_table=WIDE_DETAIL_TABLE, category="measure"),
    FieldDef(name="alarm_value",      alias_cn="报警/统计数据",            data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="measure"),
    FieldDef(name="freeze_frame",     alias_cn="冻结帧",                   data_type="VARCHAR",   source_table=WIDE_DETAIL_TABLE, category="dimension"),
]
# 固定列名集合：用于 pivot_sql_builder 识别宽表列
WIDE_DETAIL_FIXED_KEYS: set[str] = {f.name for f in WIDE_DETAIL_FIXED_FIELDS}


def _top_signal_names(limit: int = 200) -> list[tuple[str, int]]:
    """返回数据库里出现频率最高的 TOP-N 个信号名"""
    try:
        from core.db_connector import get_conn
        conn = get_conn()
        sql = f"""
SELECT sig.SIGNAL_NAME, count(*) cnt
FROM TL_RMU_PS_TASK_RULE_RESULT_SIGNAL sig
WHERE sig.SIGNAL_NAME IS NOT NULL AND sig.SIGNAL_NAME <> ''
GROUP BY 1
ORDER BY cnt DESC
LIMIT {int(limit)}
"""
        rows = conn.execute(sql).fetchall()
        return [(r[0], int(r[1] or 0)) for r in rows]
    except Exception:
        return []


def get_wide_detail_fields(top_signals: int = 200) -> list[FieldDef]:
    """明细宽表完整字段：8 固定列 + 频率最高 TOP-N 信号名动态列"""
    result = list(WIDE_DETAIL_FIXED_FIELDS)
    for name, cnt in _top_signal_names(top_signals):
        result.append(FieldDef(
            name=name,
            alias_cn=f"信号: {name}",
            data_type="VARCHAR",   # 信号值本质是 VARCHAR，可按需 CAST 成数值
            source_table=WIDE_DETAIL_TABLE,
            category="measure",
            description=f"信号 {name}，出现次数约 {cnt}",
            example_values=str(cnt),
        ))
    return result


# ============================================================
# 公共接口
# ============================================================

FIELD_REGISTRY: list[FieldDef] = _FIELDS

# 表名 → 中文名映射
SOURCE_TABLES_CN: dict[str, str] = {
    "TM_RMU_PS_TASK": "任务配置表",
    "TM_RMU_PS_TASK_RULE": "规则配置表",
    "TM_RMU_PS_TASK_VEHICLE": "任务关联车辆表",
    "TM_RMU_PS_TASK_VEHICLETYPE": "车型配置表",
    "TL_RMU_PS_TASK_RULE_RESULT": "规则执行结果表",
    "TL_RMU_PS_TASK_RULE_RESULT_SIGNAL": "信号明细表",
    WIDE_DETAIL_TABLE: WIDE_DETAIL_TABLE_CN,
}


def get_fields_grouped(include_wide_detail: bool = True, wide_top_signals: int = 200) -> list[dict]:
    """按用户设定：字段列表返回 2 个分组

    1. 固定字段 — 人员(person)、车型(vehicle_type)、车辆(vehicle)、
                    任务(task)、规则名称(rule_name)、规则类型(rule_type)、
                    报警时间(alarm_time)、持续时间(duration_sec)
    2. 信号列表 — 按信号出现频率最高的 TOP-N 平铺（UDat_13、PrplsnSysAtv、IBSBatSOC 等）
    """
    from collections import OrderedDict
    groups: dict[str, dict] = OrderedDict()
    if include_wide_detail:
        # 1. 固定字段
        groups["fixed_fields"] = {
            "table_name": "fixed_fields",
            "table_name_cn": "固定字段",
            "fields": [f.model_dump() for f in WIDE_DETAIL_FIXED_FIELDS],
        }
        # 2. 信号列表
        signal_fields = get_wide_detail_fields(wide_top_signals)
        # 去掉已经作为固定字段的前 8 个，只保留动态信号列
        dynamic = [f for f in signal_fields if f.name not in WIDE_DETAIL_FIXED_KEYS]
        groups["signal_fields"] = {
            "table_name": "signal_fields",
            "table_name_cn": "信号列表",
            "fields": [f.model_dump() for f in dynamic],
        }
    return list(groups.values())


def get_fields_by_source(table_name: str) -> list[FieldDef]:
    """按源表获取字段列表"""
    return [f for f in _FIELDS if f.source_table == table_name]


def get_field_names() -> list[str]:
    """获取所有字段名"""
    return [f.name for f in _FIELDS]


def get_field(name: str) -> FieldDef | None:
    """按字段名查找"""
    for f in _FIELDS:
        if f.name == name:
            return f
    return None


def get_fields_by_category(category: str) -> list[FieldDef]:
    """按分类获取字段"""
    return [f for f in _FIELDS if f.category == category]


def get_schema_markdown(top_signals: int = 60) -> str:
    """生成 Markdown 格式的 Schema 描述（用于 Agent System Prompt）"""
    lines = ["## 明细宽表 WIDE_DETAIL 字段说明\n"]
    lines.append("| 字段名 | 中文别名 | 类型 | 分类 | 说明 |")
    lines.append("|--------|----------|------|------|------|")
    for f in WIDE_DETAIL_FIXED_FIELDS:
        lines.append(f"| {f.name} | {f.alias_cn} | {f.data_type} | {f.category} | {f.description} |")

    # 动态信号列（取前 60 个展示）
    try:
        dynamic = _top_signal_names(top_signals)
        if dynamic:
            lines.append(f"\n> 动态信号列（按出现频率 TOP-{top_signals}，实时变化）：")
            lines.append("| 字段名 | 出现次数 |")
            lines.append("|--------|----------|")
            for name, cnt in dynamic:
                lines.append(f"| {name} | {cnt:,} |")
            lines.append(f"\n> 说明：信号列名为 SIGNAL_NAME 值，信号值为 VARCHAR 类型，可通过 TRY_CAST 转换为数值。")
        else:
            lines.append("\n> 动态信号列：无数据（信号表为空）。")
    except Exception:
        lines.append("\n> 动态信号列：查询数据库获取。")

    return "\n".join(lines)


def get_schema_for_agent(top_signals: int = 60) -> str:
    """生成给 LLM 的 Schema 描述（按 WIDE_DETAIL 宽表结构）"""
    parts = [
        "你的数据来源是明细宽表 WIDE_DETAIL，结构如下：",
        "",
        "## 固定数据字段（8 个）",
        "",
    ]
    for f in WIDE_DETAIL_FIXED_FIELDS:
        parts.append(f"- `{f.name}`（{f.alias_cn}）：{f.data_type}")
    parts.append("")

    # 动态信号列
    try:
        dynamic = _top_signal_names(top_signals)
        if dynamic:
            names_str = ", ".join(f"`{n}`" for n, _ in dynamic[:20])
            if len(dynamic) > 20:
                names_str += f" 等共 {len(dynamic)} 个"
            parts.append(f"## 动态信号列（TOP-{top_signals}，按频率自动展开）")
            parts.append("")
            parts.append(f"信号列名即 SIGNAL_NAME 值，信号值为 VARCHAR 类型（可 TRY_CAST 转 DOUBLE 做数值聚合）。")
            parts.append(f"高频信号示例：{names_str}")
        else:
            parts.append("## 动态信号列：无数据。")
    except Exception:
        parts.append("## 动态信号列：查询数据库获取。")

    parts.append("")
    parts.append("## 数据来源关系")
    parts.append("- 固定 8 字段来自 5 张源表 LEFT JOIN：TL_RMU_PS_TASK_RULE_RESULT ← TM_RMU_PS_TASK_RULE ← TM_RMU_PS_TASK ← TM_RMU_PS_TASK_VEHICLE ← TM_RMU_PS_TASK_VEHICLETYPE")
    parts.append("- 动态信号列来自 TL_RMU_PS_TASK_RULE_RESULT_SIGNAL，按 TASK_RULE_RESULT_ID 关联，以 SIGNAL_NAME 为列名 PIVOT 展开")
    parts.append("")
    parts.append("## 常用分析维度")
    parts.append("- `vehicle_type`（车型）、`rule_name`（规则名称）、`rule_type`（规则类型：统计/报警/事件）、`task`（任务名称）、`person`（人员）")
    parts.append("- 时间：`alarm_time`（报警时间，可用 date_trunc 做时间粒度聚合）、`duration_sec`（持续秒数）")
    parts.append("- 聚合：可用 count(*) 做计数，或对任意信号列用 TRY_CAST 转数值后做 sum/avg/min/max")
    return "\n".join(parts)
