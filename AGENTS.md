# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

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

代码已基本开发完成。核心流程：前端生成 PivotConfig → 调用外部 Pivot API 执行查询 → 前端 Vega-Lite 渲染图表。元数据由 SQLite 管理，支持多看板、多用户、多会话。

## 数据库核心信息

### 元数据库 SQLite（`backend/ai_data.db`）

| 表 | 用途 |
|---|---|
| `users` | 默认 3 用户：管理员、分析员、查看者 |
| `boards` | 看板，与 users 关联 |
| `charts` | 图表配置，与 boards 关联 |
| `chat_sessions` | AI 对话会话 |
| `chat_messages` | 消息记录（含 charts_json / suggestions_json） |
| `fields` | 字段注册表 |

### 外部 Pivot API 数据源

- 查询端点：`POST http://127.0.0.1:8080/api2/pivot/query`
- 筛选下拉端点：`GET http://127.0.0.1:8080/api2/pivot/select`

### 字段注册表

- **固定字段**（dimension 类）：person, vehicle_type, vehicle, task, rule_name, rule_type, alarm_time, duration_sec 等
- **动态信号列**（measure 类）：从 wide_fields.json 导入，数量可达 200+，均为 VARCHAR 类型

## 目录结构

```
/backend
  /core
    chat_db.py                   # SQLite 元数据库 CRUD
    field_registry.py             # 字段注册表
  /agents
    pivot_agent.py               # LangGraph Agent
  /routers
    api_chat.py                  # POST /api/chat
    api_charts.py                # GET/POST/PUT/DELETE /api/charts
    api_boards.py                # GET/POST/PUT/DELETE /api/boards
    api_sessions.py              # GET/POST/PUT/DELETE /api/chat/sessions
    api_admin.py                 # GET /api/fields
    api_recommend.py             # POST /api/recommend-chart
    api_auth.py                  # GET /api/auth/users
  /llm
    __init__.py                  # 私有 LLM OAuth2 认证
  /models
    __init__.py                  # 统一导出
    pivot_config.py              # 全部 Pydantic 模型
  main.py                        # FastAPI 入口
  run.py                         # 生产运行入口
  build_package.py               # PyInstaller 打包脚本

/frontend
  /src
    /stores
      useChartStore.ts           # 图表 CRUD
      useBoardStore.ts           # 看板 CRUD
      useChatStore.ts            # AI 对话状态管理
    /components
      ChartBoard.vue             # 看板网格视图
      AIDialog.vue               # AI 全屏对话框
      ChatBox.vue                # AI 对话面板
      ConfigPanel.vue            # 报表配置面板
      VegaLiteRenderer.vue       # 图表渲染
      FilterSelectDialog.vue     # 筛选器弹窗
      ResultListDialog.vue       # 结果详情弹窗
      ChartDataDialog.vue        # 图表数据查看
      ChartSqlDialog.vue         # SQL 查看
      SaveToBoardDialog.vue      # 保存到看板
    /views
      BoardView.vue              # 主视图
    /types
      index.ts                   # 类型定义
    /api
      filterSelect.ts            # 筛选下拉 API
    /constants
      filterDropdown.ts
      filterSelectDialog.ts
      mockBoardCharts.ts
      resultList.ts
    /utils
      boardSlots.ts              # 看板槽位映射
      reportConfigStorage.ts     # 配置本地缓存
      pivotConfigImport.ts       # JSON 导入
    main.ts                      # 入口
    App.vue                      # 根组件
  vite.config.ts
```

## 关键实现约定

### 后端

- `pivot_agent.py` 数据流：`intent_recognition → 路由(chat→format_reply, chart→analyze→validate→execute→format_reply, rule→analyze_rule→format_reply)`
- Agent 使用 Structured Output（`AgentOutput` 模型），私有 LLM 兜底手动 JSON 解析
- 配置校验后失败回流 analyze 重试（最多 1 次）
- 执行节点：HTTP POST 调用外部 `/api2/pivot/query`
- Agent 链路日志保存至 `agent_logs/agent_{session_id}.json`

### 前端

- 主视图 `BoardView.vue`：三栏布局（看板侧栏 + 图表网格 + 配置侧栏）
- 看板网格 `ChartBoard.vue`：2×3 槽位，slot map localStorage 持久化
- 配置面板 `ConfigPanel.vue`：字段列表 + 四象限拖拽 + 筛选 + 排序 + 分页 + 图表类型
- `vite.config.ts` 代理：`/api → localhost:8000`，`/api2 → 127.0.0.1:8080`
- 每看板最多 6 图表

## 环境变量（`.env`）

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1

LLM_PROVIDER=private
PRIVATE_LLM_API_URL=https://...
PRIVATE_LLM_MODEL=qwen-27b
PRIVATE_LLM_CLIENT_ID=...
PRIVATE_LLM_CLIENT_SECRET=...
PRIVATE_LLM_TOKEN_URL=https://...

PIVOT_API_URL=http://127.0.0.1:8080/api2/pivot/query
HOST=0.0.0.0
PORT=8000
```

## 常用命令

```bash
cd backend && source .venv/bin/activate
python main.py                  # 开发模式
python run.py                   # 生产模式

cd frontend
npm run dev
npm run build

cd backend && source .venv/bin/activate
python build_package.py         # PyInstaller 打包
```

## 关键演进记录

- **已删除**：`db_connector.py`, `db_initializer.py`, `pivot_sql_builder.py`, `api_pivot.py`
- **元数据迁移**：charts.json → SQLite
- **Agent 演进**：NL2SQL → 结构化输出 PivotConfig + HTTP 调用外部 API 执行
- **前端演进**：Dashboard + DragDropZone → BoardView + ChartBoard + ConfigPanel + AIDialog
