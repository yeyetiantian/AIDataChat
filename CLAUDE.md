# CLAUDE.md

本文件向 Claude Code (claude.ai/code) 提供本仓库的代码指引。

## 项目概览

**企业级数据透视分析系统** — Web 版数据透视分析系统，对标 Tableau/Excel 透视表，以图表可视化为主、数据表格为辅。

- **核心交互**：看板式图表管理 + AI 对话式（自然语言生成图表配置）+ 配置面板拖拽
- **数据源**：外部 Pivot API（`http://127.0.0.1:8080/api2/pivot/query`）执行实际查询
- **元数据存储**：SQLite `backend/ai_data.db`（用户、会话、消息、图表、看板、字段注册表、Agent Trace、外部维表）
- **外部维表**：SQLite 从 DuckDB 同步的维表（任务、规则、车辆、车型、规则-信号关系、信号统计），供 Agent 上下文注入
- **AI 引擎**：LangGraph Agent（意图识别 → 5 个子 Agent 分发：chart/dashboard/rule/dtc/chat）
- **Agent 链路监控**：TraceCollector 全链路 Span 树 → 存储到 SQLite `trace_spans` 表 + JSON 文件落盘，从接口层到各节点完整 I/O
- **LLM 支持**：OpenAI（默认）/ DeepSeek / 私有 LLM（OAuth2 client_credentials，含 apiTag/clientRequestId 供应商定制头）
- **后端**：FastAPI + LangGraph + Pydantic v2 + SQLite + 线程本地连接
- **前端**：Vue 3 (Composition API) + Pinia + Element Plus + vega-embed
- **打包**：PyInstaller（`build_package.py` → Onedir 分发）

## 项目当前状态

代码已基本开发完成。核心流程：前端看板拖拽配置 / AI 对话 → 生成 PivotConfig → 调用外部 Pivot API 执行查询 → 前端 Vega-Lite 渲染图表。元数据由 SQLite 管理，支持多看板、多用户、多会话。

## 数据库核心信息

### 元数据库 SQLite（`backend/ai_data.db`）

| 表 | 用途 |
|---|---|
| `users` | 默认 3 用户：管理员、分析员、查看者 |
| `boards` | 看板，与 users 关联 |
| `charts` | 图表配置，与 boards 关联（含 board_id 外键） |
| `chat_sessions` | AI 对话会话（含 mode: chart/rule） |
| `chat_messages` | 消息记录（含 charts_json / suggestions_json / ask_questions_json） |
| `fields` | 字段注册表（从 hardcoded seed 导入，含固定字段 + 动态信号列，category 分类） |
| `trace_spans` | Agent 链路追踪（Span 树 JSON，用于监控 API） |
| `agent_drafts` | Agent 交互式问卷草案（dashboard 订单暂存） |
| `freeze_functions` | 数据冻结函数库（供 rule_agent 推荐） |
| `ext_tasks` | 外部任务维表（从 DuckDB 同步，用于 Agent 上下文注入） |
| `ext_rules` | 外部规则维表（同上） |
| `ext_vehicles` | 外部车辆维表（含 VIN） |
| `ext_vehicle_types` | 外部车型维表 |
| `rule_signals` | 规则与信号的确定性关系表（从 ext_rules 解析回填） |
| `signal_stats` | 信号统计表（从 DuckDB 提取：信号名/类型/归属规则/报警次数），27K 行 |

> 数据库使用 `threading.local()` 实现线程本地连接，PRAGMA journal_mode=DELETE。

### 外部 Pivot API 数据源

- 查询端点：`POST http://127.0.0.1:8080/api2/pivot/query`
- 筛选下拉端点：`GET http://127.0.0.1:8080/api2/pivot/select`
- 请求体：PivotConfig JSON（filters/axes/legend/values 等）
- 响应：含 data/columns/total/vega_spec/sql/execution_time_ms

### 字段注册表（通过 `GET /api/fields` 暴露）

- **固定字段**（dimension/time/measure 类）：person, vehicle_type, vehicle, task, task_type, task_status, rule_name, rule_type, condition_met_time, alarm_time, duration_sec, create_time, trigger_time 等
- **动态信号列**（measure 类，VARCHAR 类型）：从 `backend/data/wide_fields.json` 首次导入 SQLite fields 表后改为 hardcoded seed 数据，数量可达 200+

## 目录结构

```
/backend
  /core
    chat_db.py                   # SQLite 元数据库（用户/会话/图表/看板/字段/Trace 的 CRUD，含外部维表初始化）
    field_registry.py             # 字段注册表（从 SQLite 读取，供 API 和 Agent 使用）
  /agents
    __init__.py                   # 空包文件
    pivot_agent.py                # 主入口 Agent：意图识别（chat/chart/rule/dashboard/dtc）→ 分发给子 Agent
    chart_agent.py                # 单图表生成子 Agent（analyze → validate → execute → format_reply），无重试
    dashboard_agent.py            # 看板多图表生成子 Agent（check_completeness → generate_charts → execute → format_reply），含交互式问卷
    rule_agent.py                 # 规则函数推荐子 Agent（analyze_rule → format_reply）
    chat_agent.py                 # 闲聊子 Agent（chat_reply → format_reply）
    dtc_agent.py                  # DTC 故障码查询子 Agent
    llm_utils.py                  # LLM 工具模块：全局 LLM 缓存、StructuredOutput、JSON 解析、TraceCollector/SpanNode
  /services
    query_preprocessor.py         # 用户查询预处理器：规则代码从自然语言提取结构化中间语言注入 LLM prompt
    chart_type_specs.py           # 图表类型字段规格注册表（各图表类型的 axes/values/legend 约束定义）
    rule_knowledge.py             # 规则知识库：规则分类/说明/示例
    rule_validator.py             # 规则表达式校验器
  /routers
    api_chat.py                  # POST /api/chat — AI 对话（含会话历史管理，支持 DB 模式/内存模式，历史 20 条截断）
    api_charts.py                # GET/POST/PUT/DELETE /api/charts — 图表 CRUD
    api_boards.py                # GET/POST/PUT/DELETE /api/boards — 看板 CRUD
    api_sessions.py              # GET/POST/PUT/DELETE /api/chat/sessions — 会话管理（含 mode 更新、消息查询）
    api_admin.py                 # GET /api/fields — 字段列表；POST /api/admin/refresh_wide_detail；POST /api/admin/reset-fields；GET /api/admin/health
    api_recommend.py             # POST /api/recommend-chart — 图表类型推荐（基于 chart_type_specs 规则引擎）
    api_functions.py             # GET /api/functions/tasks — 任务列表；GET /api/functions/rules — 规则列表；GET /api/functions/signals — 信号列表
    api_auth.py                  # GET /api/auth/users — 用户列表（无登录认证）
    api_monitor.py               # GET /api/monitor/traces — Agent Trace 监控查询（摘要/详情/统计）
  /llm
    __init__.py                  # 私有 LLM OAuth2 认证（client_credentials 模式，含 apiTag 等供应商定制头）
  /models
    __init__.py                  # 统一导出
    pivot_config.py              # Pydantic 模型：FilterItem, AxisItem, LegendItem, ShowAs,
                                 # ValueItem, FilterOnAgg, OrderBy, PivotConfig, PivotResponse,
                                 # RuleRecommendation, ChatRequest, ChatResponse
    dashboard_draft.py           # 结构化看板草案：DashboardRequestDraft, DashboardChartSlot
    dashboard_recommendation.py  # 看板推荐模型
    rule_recommendation.py       # 规则推荐模型
  /data
    wide_fields.json             # 字段注册表源文件（首次启动导入到 SQLite，后续用 hardcoded seed 替代）
  main.py                        # FastAPI 入口 + lifespan 事件（包含 CORS、路由注册、前端静态文件挂载）
  run.py                         # 生产运行入口（自动加载 .env + 打开浏览器）
  build_package.py               # PyInstaller 打包脚本（含 duckdb/httpx/openai 等二进制依赖收集）
  agent_logs/                    # Agent 链路日志目录（自动创建），JSON 格式与数据库双写

/frontend
  /src
    /stores
      useChartStore.ts           # 图表 CRUD + 看板槽位管理（userId 从 localStorage 读取 ai_chat_user_id）
      useBoardStore.ts           # 看板 CRUD + 自动切换
      useChatStore.ts            # AI 对话状态管理（会话、消息、用户切换、ask_questions/pending_step）
    /components
      ChartBoard.vue             # 看板网格视图（2×3 槽位、选择态、导出 PNG、支持草稿/占位符卡片）
      AIDialog.vue               # AI 全屏对话框（历史会话侧栏 + 消息列表 + 图表渲染 + 建议问题 + 问卷交互）
      ChatBox.vue                # AI 对话面板（被 AIDialog 内嵌使用，底部输入框 + 建议标签）
      ConfigPanel.vue            # 报表配置面板（固定字段/信号列表并排、四象限拖拽、筛选器、排序、总计/小计、分页、图表类型）
      VegaLiteRenderer.vue       # Vega-Lite 图表渲染（支持全屏/数据查看/SQL/导出 PNG/SVG，暴露 openDataDialog/toggleFullscreen/exportPng/exportSvg）
      FilterSelectDialog.vue     # 筛选器下拉弹窗选择（支持关键字搜索）
      ResultListDialog.vue        # 结果详情列表弹窗（VIN 选择筛选）
      ChartDataDialog.vue         # 图表数据查看弹窗
      ChartSqlDialog.vue          # SQL 查看弹窗
      SaveToBoardDialog.vue       # 保存到看板弹窗
      AskQuestionsPanel.vue       # 看板需求问卷面板（图表数量/任务选择/规则信号拖拽/时间范围/图表槽位）
      TraceSpanNode.vue           # Agent Trace Span 树可视化组件
    /views
      BoardView.vue              # 主视图（看板侧栏 200px + 图表网格 + 配置侧栏 368px + AI 按钮）
    /types
      index.ts                   # 完整类型定义（额外 TopN/Pagination/CalculatedField/CalculatedItem/RequestMeta）
    /api
      filterSelect.ts            # 筛选下拉 API 封装（硬编码 http://127.0.0.1:8080/api2/pivot/select）
    /constants
      filterDropdown.ts          # 筛选器字段分类常量（时间/数值/字符串/API 下拉分类）
      filterSelectDialog.ts      # 筛选弹窗列配置
      mockBoardCharts.ts         # 模拟图表数据
      resultList.ts              # 结果列表数据
    /utils
      boardSlots.ts              # 看板槽位映射（localStorage 持久化，支持 6 槽位）
      reportConfigStorage.ts     # 报表配置本地存储
      pivotConfigImport.ts       # JSON 导入 PivotConfig 反推
    main.ts                      # 入口
    App.vue                      # 根组件（标题栏 + 用户切换）
  vite.config.ts                 # Vite 配置（API 代理 /api → 8000, /api2 → 8080）
```

## 关键实现约定

### AI Agent 数据流向

```
用户输入 → POST /api/chat → pivot_agent.process_chat() → 意图识别（5 分类）→

  chart     → chart_agent      (analyze → validate → execute → format_reply)
             单图表，无重试，调用 Pivot API 失败直接返回

  dashboard → dashboard_agent  (check_completeness → generate_charts → execute → format_reply)
             多图表，LLM 完善度检查 → 问卷交互或自动提取 chart_infos → 批量生成配置 → 批量执行

  rule      → rule_agent       (analyze_rule → format_reply)
             从 freeze_functions 表读取函数库推荐

  dtc       → dtc_agent        (analyze_dtc → format_reply)
             查询 dtc_info / dtc_trigger 表数据

  chat      → chat_agent       (chat_reply → format_reply)
             友好闲聊回复

Trace 全链路监控：
  pivot_agent 创建 TraceCollector → 意图识别 span → 子 Agent span → 各节点 span
  → 完整 Span 树保存至 SQLite trace_spans 表 + agent_logs/{agent}_{session_id}.json
  每个 span 记录原始完整 I/O（输入消息、输出响应），无截断
```

### 后端

- `pivot_agent.py` 核心数据流：`intent_recognition（IntentOutput: chat/chart/rule/dashboard/dtc 五分类）→ 路由分发（5个子Agent）`
- `pivot_agent.py` 创建全链路 TraceCollector，覆盖 API 请求到子 Agent 执行完成
- `chart_agent.py`：单图表生成，`analyze→validate→execute→format_reply`，**调用 Pivot API 失败不重试**
- `dashboard_agent.py`：多图表看板生成，`check_completeness→generate_charts→execute→format_reply`
  - `check_completeness`：LLM 分析信息完善度 + 提取 chart_infos（图表描述列表）；有 draft 时直接提取
  - `generate_charts`：根据 chart_infos 调用 LLM 批量生成 PivotConfig
  - 调用 Pivot API 失败不重试
- `rule_agent.py`：`analyze_rule→format_reply`，从 `freeze_functions` 表读取函数库
- `chat_agent.py`：`chat_reply→format_reply`，简洁回答
- `dtc_agent.py`：`analyze_dtc→format_reply`，查询 DTC 故障码/触发记录

### 查询预处理层（query_preprocessor.py）

在 LLM 调用之前，通过规则代码从自然语言中提取结构化图表需求（ParsedChartRequest），
注入到 LLM prompt 中作为约束，让 LLM 只需做"结构化描述→PivotConfig"的映射：

- 图表类型（柱状/折线/饼图等 6 种）
- 时间范围（绝对日期 / 相对时间：最近N天/周/月）
- 行维度（横轴/X轴、信号名称）
- 图例（用X做图例、按X分组）
- 指标（报警次数、时长、占比等）
- 任务引用（[名称_ID]、TASK_ID=xxx）
- 信号括号格式支持：`[]`、`【】`、`""`、`（）`

测试脚本：`backend/test_preprocessor.py`（30 个测试用例覆盖）

### Agent 通用机制

- 所有 Agent 使用 Structured Output（`AgentOutput` / 各自专用模型），私有 LLM 兜底 `PydanticOutputParser` + `try_parse_json` 手动解析
- 配置 normalize：`_deep_normalize_chart` 处理 filters（只保留固定字段，value 转数组，op 合法性校验）、legend（字段来源校验）、order_by（只保留 value_fields 中字段）
- 执行节点：通过 HTTP POST 同步调用外部 `POST /api2/pivot/query` 查询数据（`requests.post`，60s 超时）
- Agent 链路日志：完整 Span 树保存至 `SQLite trace_spans` 表 + JSON 文件落盘 `agent_logs/{agent}_{session_id}.json`
- 全局缓存：LLM 实例、StructuredOutput（按模块限定名缓存）、Schema 文本、System Prompt（减少重复构造）
- 数据库线程安全：使用 `threading.local()` 实现线程本地数据库连接

### Trace 全链路追踪

TraceCollector 从 `pivot_agent.process_chat()` 创建根 Span，覆盖完整请求：

```
pivot_agent (根 Span) ← 包含完整请求上下文 + 返回结果
├── intent_recognition  ← LLM 意图分类（输入：用户消息 → 输出：intent+reason）
└── chart_agent / dashboard_agent / rule_agent / chat_agent / dtc_agent
    ├── analyze / generate_charts / ...  ← LLM 调用（完整 Prompt + 原始输出）
    ├── validate (如有)                   ← 配置校验（完整配置输入）
    ├── execute Pivot API                 ← HTTP 调用（完整请求体 + 响应体）
    └── format_reply                      ← 结果格式化（完整回复文本）
```

每个 Span 记录：
- `input`：原始输入（消息全文、配置列表等）
- `output`：原始输出（LLM 响应、API 返回体等）
- `messages`：LLM 调用时记录完整 Prompt（system+history+user）
- `duration_ms`：执行耗时
- 所有数据无截断

### 数据模型

`PivotConfig` 严格包含以下属性：

| 属性 | SQL 子句 | 说明 |
|------|----------|------|
| `filters` | WHERE | 筛选器（field/op/value），op 支持 lt/gt/gte/lte/between/in |
| `axes` | GROUP BY | 行维度，支持 aggregation 时间粒度（day/week/month/year） |
| `legend` | PIVOT ON | 列维度/图例 |
| `values` | 聚合值 | field + aggregation（count/sum/avg/min/max/source），支持 show_as |
| `having` | HAVING | 聚合后过滤 |
| `order_by` | ORDER BY | 排序 |
| `limit` | LIMIT | 最大返回条数（默认 1000） |
| `grand_total` | — | 是否显示总计 |
| `subtotals` | — | 是否显示小计 |
| `chart_type` | — | bar/line/area/point/pie/radar |

### 前端

- 主视图 `BoardView.vue`：三栏布局（看板侧栏 200px + 图表网格 + 配置侧栏 368px）
- 看板网格 `ChartBoard.vue`：2×3 槽位，支持选择态、拖拽排序、slot map 持久化（localStorage），支持草稿卡片（`isDraft`）和占位符卡片（`isPlaceholder`）
- 配置面板 `ConfigPanel.vue`：字段列表（固定字段 + 信号列表并排）、四象限拖拽（filters/axes/legend/values）、筛选器（时间/数值/字符串/API 下拉分类）、排序、总计/小计、分页、图表类型选择
- AI 对话 `AIDialog.vue`：全屏弹窗，左侧历史会话侧栏，右侧消息列表 + 图表渲染 + 建议问题 + 交互式问卷（ask_questions）
- 图表渲染 `VegaLiteRenderer.vue`：vega-embed 渲染，支持全屏、数据查看、SQL 查看、导出 PNG/SVG；通过 ref handle 暴露 `openDataDialog`/`toggleFullscreen`/`exportPng`/`exportSvg` 方法
- 看板问卷 `AskQuestionsPanel.vue`：图表数量选择、任务搜索、规则/信号标签（可拖拽到图表槽）、时间范围选择、多 Tab 图表配置
- `vite.config.ts` 代理：`/api → localhost:8000`（后端），`/api2 → 127.0.0.1:8080`（Pivot API）
- **不锁图表库**：配置项传给 `v-chart` 组件内部使用 vega-embed 渲染，仅输出 Vega-Lite 规范
- `element-plus` 作为辅助 UI 组件
- 每个看板最多 6 个图表（`MAX_BOARD_CHARTS`）
- 用户 ID 管理：`useChartStore.getUserId()` 从 `localStorage` 读取 `ai_chat_user_id` 键（默认 1）
- 筛选下拉 API：`filterSelect.ts` 硬编码 `http://127.0.0.1:8080/api2/pivot/select`（绕过 Vite 代理直接访问 Pivot API）

### 前端类型定义（`types/index.ts`）

与后端 `PivotConfig` 对齐但更丰富：
- 额外 `TopN`（top/bottom N）、`Pagination`（page/pageSize）、`CalculatedField`（公式字段）、`CalculatedItem`、`RequestMeta`
- `ValueItem` 含 `id`（前端拖拽标识）、`expr`（直接表达式，与 field 互斥）、`isSignal`（是否来自信号列表）、`aggregation` 支持 `count_distinct`、`show_as`（显示方式）
- `FilterItem` 含 `isSignal`（来自信号区的筛选器）、`filter_type`、`alias`、`select_ts`、`select_order` 等前端专用字段
- `AxisItem` 支持 `group`（时间粒度分类：year/quarter/month/week/day/hour）、`sort`（升序/降序）、`isSignal`
- `LegendItem` 含 `isSignal`
- `ChatMessage` 前端版含 `vega_spec`、`pivot_config`、`charts`、`suggestions`、`ask_questions`、`pending_step`
- `FieldDef` 前端版含 `category`（id/dimension/measure/time/status/file/ext）
- `PivotConfig` 前端版额外字段：`top_n`、`row_filters`、`col_filters`、`pagination`、`calculated_fields`、`calculated_items`、`request_meta`

## 环境变量（`.env`）

```bash
# OpenAI（默认 LLM 方案）
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1

# 私有 LLM（OAuth2 client_credentials 模式）
LLM_PROVIDER=private
PRIVATE_LLM_API_URL=https://...
PRIVATE_LLM_MODEL=qwen-27b
PRIVATE_LLM_CLIENT_ID=...
PRIVATE_LLM_CLIENT_SECRET=...
PRIVATE_LLM_TOKEN_URL=https://...

# 外部 Pivot API
PIVOT_API_URL=http://127.0.0.1:8080/api2/pivot/query

# 服务配置
HOST=0.0.0.0
PORT=8000
ENV=development               # 环境标识（dev/production，仅日志输出用）
```

## 常用命令

```bash
# 后端（激活虚拟环境后）
cd backend
source .venv/bin/activate
python main.py                  # 开发模式（reload 自动）
python run.py                   # 生产模式（自动打开浏览器）

# 前处理器测试
cd backend && source .venv/bin/activate
python test_preprocessor.py              # 全部 30 条测试用例

# 前端
cd frontend
npm run dev                     # 开发服务器（代理 /api → 8000, /api2 → 8080）
npm run build                   # 构建到 dist/

# 打包（后端可执行文件）
cd backend && source .venv/bin/activate
python build_package.py         # PyInstaller → package_output/AIDataChat/

# 字段注册表数据文件
# backend/data/wide_fields.json  # 首次启动自动导入 SQLite，也可手动编辑
```

## API 路由一览

| 方法 | 路由 | 模块 | 说明 |
|------|------|------|------|
| POST | `/api/chat` | `api_chat.py` | AI 对话（含 DB/内存双模式、history 截断 20 条、看板问卷草稿） |
| GET | `/api/fields` | `api_admin.py` | 字段列表（固定字段 + 信号列表分组） |
| POST | `/api/admin/refresh_wide_detail` | `api_admin.py` | 手动触发宽表重建（遗留） |
| POST | `/api/admin/reset-fields` | `api_admin.py` | 重置字段为 hardcoded 数据 |
| GET | `/api/admin/health` | `api_admin.py` | 健康检查 |
| GET/POST | `/api/charts` | `api_charts.py` | 图表 CRUD（?board_id= 筛选） |
| PUT/DELETE | `/api/charts/{chart_id}` | `api_charts.py` | 单图表更新/删除 |
| GET/POST | `/api/boards` | `api_boards.py` | 看板 CRUD（?user_id= 筛选） |
| PUT/DELETE | `/api/boards/{board_id}` | `api_boards.py` | 单看板更新/删除 |
| GET/POST/PUT/DELETE | `/api/chat/sessions` | `api_sessions.py` | 会话管理（含 mode 更新、消息查询） |
| POST | `/api/recommend-chart` | `api_recommend.py` | 图表类型推荐（基于 chart_type_specs 规则引擎） |
| GET | `/api/auth/users` | `api_auth.py` | 用户列表（无密码/无登录认证） |
| GET | `/api/monitor/traces` | `api_monitor.py` | Agent Trace 摘要列表 |
| GET | `/api/monitor/traces/{trace_id}` | `api_monitor.py` | 完整 Trace 详情（含 Span 树） |
| GET | `/api/monitor/traces/sessions/list` | `api_monitor.py` | 有 Trace 的会话列表 |
| GET | `/api/monitor/stats` | `api_monitor.py` | Trace 统计（total/success/error） |
| GET | `/api/functions/tasks` | `api_functions.py` | 任务列表（支持 keyword 搜索） |
| GET | `/api/functions/rules` | `api_functions.py` | 规则列表（支持 task_id 筛选） |
| GET | `/api/functions/signals` | `api_functions.py` | 信号列表（支持 task_id 筛选） |
| GET | `/` | `main.py` | 服务信息 / Python 环境：挂载前端静态文件 |

## 关键演进记录

- **原方案**：DuckDB 宽表 WIDE_DETAIL + 自建 SQL Builder → 被当前外部 Pivot API 方案替代
- **已删除的文件**：`db_connector.py`, `db_initializer.py`, `pivot_sql_builder.py`, `api_pivot.py`, `chart_data_quality.py`
- **元数据迁移**：charts.json → SQLite（`chat_db.py` 统一管理）
- **Agent 演进**：NL2SQL → 结构化输出 PivotConfig + HTTP 调用外部 API 执行
- **Agent 拆分**：原 chart_agent 单 Agent 兼顾单图表+看板 → 拆分为 chart_agent（单图表）+ dashboard_agent（多图表看板）
- **添加 DTC Agent**：新增 dtc_agent 处理 DTC 故障码查询
- **查询预处理器**：新增 query_preprocessor 规则引擎，从自然语言提取结构化中间语言注入 LLM prompt
- **Trace 全链路追踪**：TraceCollector 从 pivot_agent 开始，覆盖意图识别→子 Agent→各节点，记录完整 I/O 无截断
- **前端演进**：Dashboard + DragDropZone → BoardView + ChartBoard + ConfigPanel + AIDialog
- **详细数据库文档**：[vcloud_duck_数据库文档.md](vcloud_duck_数据库文档.md)
- **完整需求**：[需求说明.md](需求说明.md)
