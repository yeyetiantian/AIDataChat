# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

**企业级数据透视分析系统** — Web 版数据透视分析系统，对标 Tableau/Excel 透视表，以图表可视化为主、数据表格为辅。

- **核心交互**：拖拽式（四象限拖拽生成图表）+ AI 对话式（自然语言生成图表配置）
- **数据库**：DuckDB `vcloud_duck.db`（7.3 GB，6 张表，104 字段，约 2.95 亿行）
- **后端**：FastAPI + DuckDB + LangGraph + Pydantic v2
- **前端**：Vue 3 (Composition API) + Pinia + vue-draggable-plus + vega-embed + Element Plus

## 项目当前状态

此项目尚**未编写代码**，仅有数据库文件和需求文档。后续开发将严格按以下阶段顺序推进：

1. **第一阶段** — 宽表初始化（db_initializer + field_registry）
2. **第二阶段** — 后端 SQL 生成器（pivot_sql_builder + pivot_config 模型）
3. **第三阶段** — 后端 API（/api/pivot, /api/chat, /api/admin/refresh_wide_table）
4. **第四阶段** — 前端（Pinia Store + DragDropZone + VegaLiteRenderer + ChatBox）
5. **第五阶段** — 联调优化

## 数据库核心信息

### 表关系

```
TM_RMU_PS_TASK (714 行)
├── TM_RMU_PS_TASK_VEHICLETYPE (714 行)
│   └── TM_RMU_PS_TASK_VEHICLE (13,163 行)
├── TM_RMU_PS_TASK_RULE (3,109 行)
│   └── TL_RMU_PS_TASK_RULE_RESULT (13,591,531 行)
│       └── TL_RMU_PS_TASK_RULE_RESULT_SIGNAL (281,747,993 行)
```

### 核心架构决策

- **启动时构建明细宽表 WIDE_DETAIL**：FastAPI 启动时检测 `WIDE_DETAIL` 是否存在，不存在则后台线程创建
- **宽表结构**：8 个固定业务字段（person/vehicle_type/vehicle/task/rule_name/rule_type/alarm_time/duration_sec）+ TOP-N 动态信号列（按 SIGNAL_NAME 出现频率平铺，默认 200 个）
- **索引列**：alarm_time, person, vehicle_type, vehicle, task, rule_name, rule_type
- **查询数据源**：物化表 `WIDE_DETAIL` 或 Pivot 场景中以 CTE 实时构建
- **NL2SQL**：LangGraph Agent，system prompt 注入 WIDE_DETAIL 字段 Schema（固定8字段 + TOP-60 信号列）

### 配置文件

详细数据库文档见 [vcloud_duck_数据库文档.md](vcloud_duck_数据库文档.md)，完整需求见 [需求说明.md](需求说明.md)。

## 目录结构

```
/backend
  /core
    build_wide_table.py          # CLI: python -m core.db_initializer（宽表构建入口）
    db_connector.py              # DuckDB 连接管理（读写分离）
    db_initializer.py            # WIDE_DETAIL 明细宽表构建（供 CLI 和 API 共用）
    pivot_sql_builder.py         # SQL 生成器（CTE 流水线：9 步，支持 WIDE_DETAIL）
    field_registry.py            # 明细宽表字段字典（固定8字段 + 动态信号列）
  /agents
    pivot_agent.py               # LangGraph Agent（保留完整链路日志至 agent_logs/）
  /routers
    api_pivot.py                 # POST /api/pivot
    api_chat.py                  # POST /api/chat
    api_admin.py                 # POST /api/admin/refresh_wide_detail, GET /api/fields, GET /api/schema, GET /api/admin/health
  /models
    __init__.py                  # Pydantic 模型（严格 4 属性 JSON）
  main.py                        # FastAPI 入口 + lifespan 事件
  .env.example                   # 环境变量模板
  agent_logs/                    # Agent 链路日志目录（自动创建）

/frontend
  /src
    /stores
      usePivotStore.ts           # Pinia 状态管理
    /components
      DragDropZone.vue           # 四象限拖拽区
      FieldList.vue              # 字段列表
      VegaLiteRenderer.vue       # 图表渲染（vega-embed）
      ChatBox.vue                # AI 对话面板
    /views
      Dashboard.vue              # 主界面
    /types
      index.ts                   # 类型定义
    main.ts                      # 入口
    App.vue                      # 根组件
  vite.config.ts                 # Vite 配置（含 API 代理）
  index.html
  package.json
  tsconfig.json
  env.d.ts
```

## 关键实现约定

### 后端

- `pivot_sql_builder.py` 的 SQL 生成流水线共 9 步（Base CTE → 分组聚合 → 动态列名 → Show As → HAVING → 总计小计 → TOP N → 排序 → 分页）
- Pivot 配置 JSON 严格四属性：`filters`（WHERE）、`axes`（GROUP BY）、`legend`（PIVOT ON）、`values`（聚合）
- 数据来源：WIDE_DETAIL 明细宽表（8 固定字段 + 动态信号列），Pivot 场景以 CTE 实时 JOIN 构建
- 支持 `expr` 字段（与 field+aggregation 互斥，直接嵌入 DuckDB 表达式）
- 对信号列做数值聚合时，使用 `TRY_CAST("信号名" AS DOUBLE)` 转换
- `functools.lru_cache` 可缓存相同配置结果
- Agent 链路日志自动保存至 `agent_logs/agent_{session_id}.json`
- 虚拟环境路径：`backend/.venv/`

### 前端

- 使用 `vega-embed` 渲染 Vega-Lite 规范，不依赖第三方图表库
- `vue-draggable-plus` 实现四象限拖拽交互（原生 HTML5 Drag & Drop）
- `element-plus` 作为辅助 UI 组件
- 开发服务器代理 `/api` 到 `localhost:8000`

## 常用命令

```bash
# 后端（激活虚拟环境后）
cd backend
source .venv/bin/activate
python main.py                  # 开发模式（reload 自动）

# 构建明细宽表 WIDE_DETAIL（首次必须执行）
cd backend && source .venv/bin/activate
python -m core.db_initializer           # 构建
python -m core.db_initializer --force    # 强制重建

# 前端
cd frontend
npm run dev

# 构建
cd frontend && npm run build
```

## 关于此文档

- 所有关键设计决策来自 [需求说明.md](需求说明.md)（最终版 v3.0）
- 数据库 Schema 来自 [vcloud_duck_数据库文档.md](vcloud_duck_数据库文档.md)
