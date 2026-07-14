# DuckDB 数据库 `vcloud_duck.db` 文档

> **文件位置：** `/Users/wanglei/Desktop/AIDataChat/vcloud_duck.db`  
> **文件大小：** 7.3 GB  
> **数据库类型：** DuckDB  
> **分析日期：** 2026-07-04

---

## 1. 整体统计

| 指标 | 数值 |
|------|:----:|
| 总表数 | **6** |
| 总字段数 | **104** |
| 总数据行数 | **295,357,224**（约 2.95 亿行） |

---

## 2. 各表概览

| # | 表名 | 字段数 | 行数 | 行数占比 | 表类型 |
|:-:|------|:------:|------:|:--------:|--------|
| 1 | `TL_RMU_PS_TASK_RULE_RESULT_SIGNAL` | 8 | **281,747,993** | 95.40% | 明细流水 |
| 2 | `TL_RMU_PS_TASK_RULE_RESULT` | 24 | **13,591,531** | 4.60% | 结果流水 |
| 3 | `TM_RMU_PS_TASK_VEHICLE` | 13 | 13,163 | <0.01% | 配置维表 |
| 4 | `TM_RMU_PS_TASK_RULE` | 23 | 3,109 | <0.01% | 配置维表 |
| 5 | `TM_RMU_PS_TASK` | 33 | 714 | <0.01% | 配置维表 |
| 6 | `TM_RMU_PS_TASK_VEHICLETYPE` | 3 | 714 | <0.01% | 配置维表 |

---

## 3. 各表字段明细

### 3.1 `TL_RMU_PS_TASK_RULE_RESULT_SIGNAL` — 规则执行结果信号明细

> **行数：** 281,747,993 ｜ **字段数：** 8 ｜ **数据占比：** 95.40%

该表是数据库中最大的表，记录了每条规则触发时产生的详细信号数据。

| # | 字段名 | 类型 | 说明 |
|:-:|--------|:----:|------|
| 1 | RULE_RESULT_SIGNAL_ID | BIGINT | 主键 ID |
| 2 | TASK_RULE_RESULT_ID | BIGINT | 关联结果 ID（FK → TL_RMU_PS_TASK_RULE_RESULT） |
| 3 | TYPE | BIGINT | 信号类型 |
| 4 | SIGNAL_NAME | VARCHAR | 信号名称 |
| 5 | VALUE | VARCHAR | 信号值 |
| 6 | EXTRA_1 | BIGINT | 扩展字段 1 |
| 7 | EXTRA_2 | VARCHAR | 扩展字段 2 |
| 8 | EXTRA_3 | VARCHAR | 扩展字段 3 |

---

### 3.2 `TL_RMU_PS_TASK_RULE_RESULT` — 规则执行结果

> **行数：** 13,591,531 ｜ **字段数：** 24 ｜ **数据占比：** 4.60%

记录每条规则的执行结果，包含多种文件类型（RBF、MF4、VSB、ASC）的上传与处理状态。

| # | 字段名 | 类型 | 说明 |
|:-:|--------|:----:|------|
| 1 | TASK_RULE_RESULT_ID | BIGINT | 主键 ID |
| 2 | TASK_RULE_ID | BIGINT | 关联规则 ID（FK → TM_RMU_PS_TASK_RULE） |
| 3 | VEHICLE_SID | BIGINT | 车辆 SID |
| 4 | VIN | VARCHAR | 车辆识别码（车架号） |
| 5 | RMU_CODE | VARCHAR | RMU 编码 |
| 6 | FILE_NAME | VARCHAR | 文件名 |
| 7 | TIME | DATE | 日期 |
| 8 | VALUE | VARCHAR | 结果值 |
| 9 | RMU_FILE_STATE | BIGINT | RMU 文件状态 |
| 10 | RBF_FILE_ID | BIGINT | RBF 文件 ID |
| 11 | RBF_STATE | BIGINT | RBF 文件状态 |
| 12 | RBF_REMARK | VARCHAR | RBF 备注 |
| 13 | MF4_FILE_ID | BIGINT | MF4 文件 ID |
| 14 | MF4_STATE | BIGINT | MF4 文件状态 |
| 15 | MF4_REMARK | VARCHAR | MF4 备注 |
| 16 | VSB_FILE_ID | BIGINT | VSB 文件 ID |
| 17 | VSB_STATE | BIGINT | VSB 文件状态 |
| 18 | VSB_REMARK | VARCHAR | VSB 备注 |
| 19 | ASC_FILE_ID | BIGINT | ASC 文件 ID |
| 20 | ASC_STATE | BIGINT | ASC 文件状态 |
| 21 | ASC_REMARK | VARCHAR | ASC 备注 |
| 22 | EXIT_TIME | TIMESTAMP | 退出时间 |
| 23 | TRIGGER_TIME | TIMESTAMP | 触发时间 |
| 24 | MASTER_ID | VARCHAR | 主 ID（可关联主控系统） |

---

### 3.3 `TM_RMU_PS_TASK` — 任务配置主表

> **行数：** 714 ｜ **字段数：** 33 ｜ **数据占比：** <0.01%

任务的基础配置信息，包括任务类型、时间窗口、审批状态、告警策略等。

| # | 字段名 | 类型 | 说明 |
|:-:|--------|:----:|------|
| 1 | TASK_ID | INTEGER | 主键 ID |
| 2 | TASK_NAME | VARCHAR | 任务名称 |
| 3 | TASK_TYPE | INTEGER | 任务类型 |
| 4 | TASK_PRIORITY | INTEGER | 任务优先级 |
| 5 | TASK_DB_MODE | INTEGER | 数据库模式 |
| 6 | TASK_START_TIME | TIMESTAMP | 任务开始时间 |
| 7 | TASK_END_TIME | TIMESTAMP | 任务结束时间 |
| 8 | TASK_EXECUTE_START_TIME | TIMESTAMP | 任务执行开始时间 |
| 9 | TASK_EXECUTE_END_TIME | TIMESTAMP | 任务执行结束时间 |
| 10 | ANALYSIS_STATE | INTEGER | 分析状态 |
| 11 | RMUDATA_STATE | INTEGER | RMU 数据状态 |
| 12 | MERGE_STATE | INTEGER | 合并状态 |
| 13 | APPROVE_STATE | INTEGER | 审批状态 |
| 14 | APPROVE_REMARK | VARCHAR | 审批备注 |
| 15 | IS_DELETE | INTEGER | 逻辑删除标记 |
| 16 | CREATE_BY | VARCHAR | 创建人 |
| 17 | CREATE_TIME | TIMESTAMP | 创建时间 |
| 18 | UPDATE_BY | VARCHAR | 更新人 |
| 19 | UPDATE_TIME | TIMESTAMP | 更新时间 |
| 20 | EXTRA1 | INTEGER | 扩展字段 1 |
| 21 | EXTRA2 | VARCHAR | 扩展字段 2 |
| 22 | EXTRA3 | VARCHAR | 扩展字段 3 |
| 23 | VESCOM_ID | INTEGER | VESCOM ID |
| 24 | IS_PUBLIC | INTEGER | 是否公开 |
| 25 | CREATE_BY_CODE | VARCHAR | 创建人工号 |
| 26 | UPDATE_BY_CODE | VARCHAR | 更新人工号 |
| 27 | REPORT_ID | INTEGER | 报表 ID |
| 28 | IS_NOTICE | INTEGER | 是否通知 |
| 29 | WARNING_TIMES | INTEGER | 告警次数 |
| 30 | CYCLE | DECIMAL(8,2) | 周期 |
| 31 | UNIT | VARCHAR | 单位 |
| 32 | WARNING_TIME | TIMESTAMP | 告警时间 |
| 33 | DATASOURCE | INTEGER | 数据源 |

---

### 3.4 `TM_RMU_PS_TASK_RULE` — 规则配置表

> **行数：** 3,109 ｜ **字段数：** 23 ｜ **数据占比：** <0.01%

每条任务下包含多条规则，配置规则的开始/结束/判定表达式、信号列表、文件截取时间窗口等。

| # | 字段名 | 类型 | 说明 |
|:-:|--------|:----:|------|
| 1 | TASK_RULE_ID | INTEGER | 主键 ID |
| 2 | TASK_ID | INTEGER | 关联任务 ID（FK → TM_RMU_PS_TASK） |
| 3 | RULE_NAME | VARCHAR | 规则名称 |
| 4 | RULE_DESCRIPTION | VARCHAR | 规则描述 |
| 5 | RULE_MODE | INTEGER | 规则模式 |
| 6 | START_EXPRESSION | VARCHAR | 开始表达式 |
| 7 | START_EXPRESSION_CONVERT | VARCHAR | 开始表达式（转换后） |
| 8 | START_EXPRESSION_ID | INTEGER | 开始表达式 ID |
| 9 | START_EXPRESSION_PARAM | VARCHAR | 开始表达式参数 |
| 10 | END_EXPRESSION | VARCHAR | 结束表达式 |
| 11 | END_EXPRESSION_CONVERT | VARCHAR | 结束表达式（转换后） |
| 12 | END_EXPRESSION_ID | INTEGER | 结束表达式 ID |
| 13 | END_EXPRESSION_PARAM | VARCHAR | 结束表达式参数 |
| 14 | JUDGE_EXPRESSION | VARCHAR | 判定表达式 |
| 15 | JUDGE_EXPRESSION_CONVERT | VARCHAR | 判定表达式（转换后） |
| 16 | JUDGE_EXPRESSION_ID | INTEGER | 判定表达式 ID |
| 17 | JUDGE_EXPRESSION_PARAM | VARCHAR | 判定表达式参数 |
| 18 | RULE_TYPE | INTEGER | 规则类型 |
| 19 | RULE_END_TIME | TIMESTAMP | 规则结束时间 |
| 20 | RBF_BEFORE_TIME | DECIMAL(18,3) | RBF 截取前时间（秒） |
| 21 | RBF_AFTER_TIME | DECIMAL(18,3) | RBF 截取后时间（秒） |
| 22 | RULE_SIGNALS | VARCHAR | 规则关联信号列表 |
| 23 | OTHER_SIGNALS | VARCHAR | 其他信号列表 |
 
---

### 3.5 `TM_RMU_PS_TASK_VEHICLE` — 任务关联车辆

> **行数：** 13,163 ｜ **字段数：** 13 ｜ **数据占比：** <0.01%

记录每个任务下需要分析的车辆列表，包含 VIN、RMU 编码及处理状态。

| # | 字段名 | 类型 | 说明 |
|:-:|--------|:----:|------|
| 1 | TASK_VEHICLE_ID | INTEGER | 主键 ID |
| 2 | TASK_VEHICLETYPE_ID | INTEGER | 关联车型 ID（FK → TM_RMU_PS_TASK_VEHICLETYPE） |
| 3 | VEHICLE_ID | INTEGER | 车辆 ID |
| 4 | TASK_ID | INTEGER | 关联任务 ID（FK → TM_RMU_PS_TASK） |
| 5 | VIN | VARCHAR | 车辆识别码（车架号） |
| 6 | VIN_PATAC_ID | VARCHAR | VIN PATAC ID |
| 7 | RMU_CODE | VARCHAR | RMU 编码 |
| 8 | STATE | INTEGER | 状态 |
| 9 | EXTRA1 | INTEGER | 扩展字段 1 |
| 10 | EXTRA2 | VARCHAR | 扩展字段 2 |
| 11 | EXTRA3 | VARCHAR | 扩展字段 3 |
| 12 | IS_DEL | INTEGER | 逻辑删除标记 |
| 13 | UPDATE_TIME | TIMESTAMP | 更新时间 |

---

### 3.6 `TM_RMU_PS_TASK_VEHICLETYPE` — 任务车型配置

> **行数：** 714 ｜ **字段数：** 3 ｜ **数据占比：** <0.01%

配置每个任务关联的车型名称。

| # | 字段名 | 类型 | 说明 |
|:-:|--------|:----:|------|
| 1 | TASK_VEHICLETYPE_ID | INTEGER | 主键 ID |
| 2 | TASK_ID | INTEGER | 关联任务 ID（FK → TM_RMU_PS_TASK） |
| 3 | VEHICLETYPE_NAME | VARCHAR | 车型名称 |

---

## 4. 表关系图

```
TM_RMU_PS_TASK (714 行)
├── TM_RMU_PS_TASK_VEHICLETYPE (714 行)     — 任务关联车型
│   └── TM_RMU_PS_TASK_VEHICLE (13,163 行)   — 任务关联车辆
├── TM_RMU_PS_TASK_RULE (3,109 行)           — 任务下的规则
│   └── TL_RMU_PS_TASK_RULE_RESULT (13,591,531 行) — 规则执行结果
│       └── TL_RMU_PS_TASK_RULE_RESULT_SIGNAL (281,747,993 行) — 结果信号明细
```

---

## 5. 数据分布特征

| 维度 | 说明 |
|------|------|
| **数据倾斜度** | 极高。两张流水表（TL_）占 99.994% 的数据量，其余 4 张配置表仅占 0.006%。 |
| **最大表** | `TL_RMU_PS_TASK_RULE_RESULT_SIGNAL`（2.82 亿行），占总行数 95.4%。 |
| **平均每结果信号的扩展字段** | `EXTRA_1`、`EXTRA_2`、`EXTRA_3` 在多个表中出现，推测为预留扩展字段。 |
| **文件处理链路** | 规则执行结果涉及 4 种文件类型（RBF / MF4 / VSB / ASC），每种均有独立的文件 ID、状态字段和备注字段。 |
| **时间范围** | 需通过实际 `TIME` / `TRIGGER_TIME` / `EXIT_TIME` 等字段确认业务覆盖时段。 |
