# CLAUDE.md

本文件向 Claude Code (claude.ai/code) 提供本仓库的代码指引。

## 项目概览

**企业级数据透视分析系统** — Web 版数据透视分析系统，对标 Tableau/Excel 透视表，以图表可视化为主、数据表格为辅。

- **核心交互**：看板式图表管理 + AI 对话式（自然语言生成图表配置）+ 配置面板拖拽
- **数据源**：外部 Pivot API（`http://127.0.0.1:8080/api2/pivot/query`）执行实际查询
- **元数据存储**：SQLite `backend/ai_data.db`（用户、会话、消息、图表、看板、字段注册表）
- **AI 引擎**：LangGraph Agent（意图识别 → 结构化输出 → 校验重试 → 执行/回复）
- **LLM 支持**：OpenAI（默认）/ 私有 LLM（OAuth2 client_credentials）
- **后端**：FastAPI + LangGraph + Pydantic v2 + SQLite
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
| `charts` | 图表配置，与 boards 关联 |
| `chat_sessions` | AI 对话会话 |
| `chat_messages` | 消息记录（含 charts_json / suggestions_json） |
| `fields` | 字段注册表（从 wide_fields.json 导入，含固定字段 + 动态信号列） |

### 外部 Pivot API 数据源

- 查询端点：`POST http://127.0.0.1:8080/api2/pivot/query`
- 筛选下拉端点：`GET http://127.0.0.1:8080/api2/pivot/select`
- 请求体：PivotConfig JSON（filters/axes/legend/values 等）
- 响应：含 data/columns/total/vega_spec/sql/execution_time_ms

### 字段注册表（通过 `GET /api/fields` 暴露）

- **固定字段**（dimension 类）：person, vehicle_type, vehicle, task, rule_name, rule_type, alarm_time, duration_sec 等
- **动态信号列**（measure 类）：从 wide_fields.json 导入，数量可达 200+，均为 VARCHAR 类型
- 字段数据来源：首次启动从 `backend/data/wide_fields.json` 导入到 SQLite fields 表

## 目录结构

```
/backend
  /core
    chat_db.py                   # SQLite 元数据库（用户/会话/图表/看板/字段的 CRUD）
    field_registry.py             # 字段注册表（从 SQLite 读取，供 API 和 Agent 使用）
  /agents
    pivot_agent.py               # LangGraph Agent（意图识别 → 分析 → 校验 → 执行 → 回复）
  /routers
    api_chat.py                  # POST /api/chat — AI 对话（含会话历史管理）
    api_charts.py                # GET/POST/PUT/DELETE /api/charts — 图表 CRUD
    api_boards.py                # GET/POST/PUT/DELETE /api/boards — 看板 CRUD
    api_sessions.py              # GET/POST/PUT/DELETE /api/chat/sessions — 会话管理
    api_admin.py                 # GET /api/fields — 字段列表
    api_recommend.py             # POST /api/recommend-chart — 图表类型推荐（规则引擎）
    api_auth.py                  # GET /api/auth/users — 用户列表
  /llm
    __init__.py                  # 私有 LLM OAuth2 认证（client_credentials 模式）
  /models
    __init__.py                  # 统一导出
    pivot_config.py              # Pydantic 模型：FilterItem, AxisItem, LegendItem, ShowAs,
                                 # ValueItem, FilterOnAgg, OrderBy, PivotConfig, PivotResponse,
                                 # RuleRecommendation, ChatRequest, ChatResponse
  /data
    wide_fields.json             # 字段注册表源文件（首次启动导入到 SQLite）
  main.py                        # FastAPI 入口 + lifespan 事件
  run.py                         # 生产运行入口（自动加载 .env + 打开浏览器）
  build_package.py               # PyInstaller 打包脚本
  agent_logs/                    # Agent 链路日志目录（自动创建）

/frontend
  /src
    /stores
      useChartStore.ts           # 图表 CRUD + 看板槽位管理
      useBoardStore.ts           # 看板 CRUD + 自动切换
      useChatStore.ts            # AI 对话状态管理（会话、消息、用户切换）
    /components
      ChartBoard.vue             # 看板网格视图（2×3 槽位、选择态、导出 PNG）
      AIDialog.vue               # AI 全屏对话框（历史会话侧栏 + 消息列表 + 图表渲染）
      ChatBox.vue                # AI 对话面板（被 AIDialog 内嵌使用）
      ConfigPanel.vue            # 报表配置面板（字段列表/四象限拖拽/筛选/排序/总计/分页/图表类型）
      VegaLiteRenderer.vue       # Vega-Lite 图表渲染（支持全屏/数据查看/SQL/导出）
      FilterSelectDialog.vue     # 筛选器下拉弹窗选择
      ResultListDialog.vue        # 结果详情列表弹窗
      ChartDataDialog.vue         # 图表数据查看弹窗
      ChartSqlDialog.vue          # SQL 查看弹窗
      SaveToBoardDialog.vue       # 保存到看板弹窗
    /views
      BoardView.vue              # 主视图（看板侧栏 + 图表网格 + 配置侧栏 + AI 按钮）
    /types
      index.ts                   # 完整类型定义（与后端 PivotConfig 对齐）
    /api
      filterSelect.ts            # 筛选下拉 API 封装
    /constants
      filterDropdown.ts          # 筛选器字段分类常量
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

### 数据流向

```
用户操作 → PivotConfig JSON → 外部 Pivot API (/api2/pivot/query) → 
  → data + columns + vega_spec → Vega-Lite 渲染
          
用户输入 → POST /api/chat → LangGraph Agent (pivot_agent.py) → 
  → 意图识别 → 分析 (AgentOutput) → 校验 (重试1次) → 
  → 执行 (HTTP 调用外部 Pivot API) → 格式化回复
```

### 后端

- `pivot_agent.py` 核心数据流：`intent_recognition → 路由(chat→format_reply, chart→analyze→validate→execute→format_reply, rule→analyze_rule→format_reply)`
- Agent 使用 Structured Output（`AgentOutput` 模型），私有 LLM 兜底手动 JSON 解析
- 配置校验：validate 节点检查 values 和 axes 非空，失败回流 analyze 重试（最多 1 次）
- 执行节点：通过 HTTP POST 调用外部 `/api2/pivot/query` 查询数据
- 意图识别：独立轻量调用 `IntentOutput`（chat/chart/rule 三分类）
- Chat 模式不生成 charts 和 suggestions；Chart 模式默认单图表，用户明确要求才多图表
- Agent 链路日志：完整保存至 `agent_logs/agent_{session_id}.json`
- 全局缓存：LLM 实例、Schema 文本、System Prompt（减少重复构造）
- 配置 normalize：filters 只保留固定字段、value 转数组、op 合法性校验；legend/order_by 字段来源校验

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
- 看板网格 `ChartBoard.vue`：2×3 槽位，支持选择态、拖拽排序、slot map 持久化（localStorage）
- 配置面板 `ConfigPanel.vue`：字段列表（固定字段 + 信号列表并排）、四象限拖拽、筛选器、排序、总计/小计、分页、图表类型选择
- AI 对话 `AIDialog.vue`：全屏弹窗，左侧历史会话侧栏，右侧消息列表 + 图表渲染 + 建议问题
- 图表渲染 `VegaLiteRenderer.vue`：vega-embed 渲染，支持全屏、数据查看、SQL 查看、导出 PNG
- `vite.config.ts` 代理：`/api → localhost:8000`（后端），`/api2 → 127.0.0.1:8080`（Pivot API）
- **不锁图表库**：配置项传给 `v-chart` 组件内部使用 vega-embed 渲染，仅输出 Vega-Lite 规范
- `element-plus` 作为辅助 UI 组件
- 每个看板最多 6 个图表（`MAX_BOARD_CHARTS`）

### 前端类型定义（`types/index.ts`）

与后端 `PivotConfig` 对齐但更丰富：
- 额外 `TopN`, `Pagination`, `CalculatedField`, `CalculatedItem`, `RequestMeta`
- `ValueItem` 含 `id`（前端拖拽标识）、`expr`（直接表达式，与 field 互斥）
- `FilterItem` 含 `isSignal`、`filter_type` 等前端专用字段
- `AxisItem` 支持 `group` 和 `sort` 属性

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
```

## 常用命令

```bash
# 后端（激活虚拟环境后）
cd backend
source .venv/bin/activate
python main.py                  # 开发模式（reload 自动）
python run.py                   # 生产模式（自动打开浏览器）

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

## 关键演进记录

- **原方案**：DuckDB 宽表 WIDE_DETAIL + 自建 SQL Builder → 被当前外部 Pivot API 方案替代
- **已删除的文件**：`db_connector.py`, `db_initializer.py`, `pivot_sql_builder.py`, `api_pivot.py`
- **元数据迁移**：charts.json → SQLite（`chat_db.py` 统一管理）
- **Agent 演进**：NL2SQL → 结构化输出 PivotConfig + HTTP 调用外部 API 执行
- **前端演进**：Dashboard + DragDropZone → BoardView + ChartBoard + ConfigPanel + AIDialog
- **详细数据库文档**：[vcloud_duck_数据库文档.md](vcloud_duck_数据库文档.md)
- **完整需求**：[需求说明.md](需求说明.md)
