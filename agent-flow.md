# Agent 流程图

```mermaid
flowchart TD
    START(["用户输入 message + history"])

    subgraph process_chat["process_chat()"]
        INIT[初始化 AgentState]
    end

    subgraph intent_recog["意图识别"]
        INTENT["intent_recognition_node\n轻量 LLM 调用 → IntentOutput"]
    end

    subgraph chart_path["图表推荐路径"]
        ANALYZE["analyze_node\nLLM 结构化输出 → AgentOutput\n生成 pivot_config + charts"]
        VALIDATE["validate_config_node\n校验 charts 合法性"]
        EXECUTE["execute_node\n遍历 charts 执行 SQL 查询"]
    end

    subgraph rule_path["规则函数推荐路径"]
        ANALYZE_RULE["analyze_rule_node\nLLM 结构化输出 → AgentOutput\n生成 rule_recommendations"]
    end

    subgraph retry_validate["校验重试（最多 1 次）"]
        V_OK{"校验通过？"}
        V_RETRY["analyze_retry_count += 1"]
        V_FAIL["校验失败\ncharts = []"]
    end

    subgraph retry_execute["SQL 重试（最多 2 次）"]
        E_ALL_FAIL{"所有图表都失败？"}
        E_RETRY["execute_retry_count += 1\n设置 sql_error"]
        E_PARTIAL["部分成功，继续"]
    end

    subgraph llm_fallback["LLM 调用降级"]
        STRUCT["with_structured_output\n返回 AgentOutput"]
        MANUAL["PydanticOutputParser\n或手动 JSON 解析"]
    end

    subgraph output["输出"]
        FORMAT["format_reply_node\n格式化回复 + 保存日志"]
        END_NODE(["返回 reply + charts + rules"])
    end

    %% 主流程
    START --> INIT
    INIT --> INTENT

    %% 意图识别 → 三路路由
    INTENT --> ROUTE{"_route_after_intent"}
    ROUTE -- chat --> FORMAT
    ROUTE -- chart --> ANALYZE
    ROUTE -- rule --> ANALYZE_RULE

    %% chart 路径
    ANALYZE --> STRUCT
    STRUCT -- 成功 --> PARSE_OK["AgentOutput"]
    STRUCT -- 失败 --> MANUAL
    MANUAL --> PARSE_OK
    PARSE_OK --> CHARTS["charts + pivot_config"]
    CHARTS --> VALIDATE

    VALIDATE --> V_OK
    V_OK -- 通过 --> EXECUTE
    V_OK -- 失败 + retry < 1 --> V_RETRY
    V_RETRY --> ANALYZE
    V_OK -- 失败 + retry >= 1 --> V_FAIL
    V_FAIL --> FORMAT

    EXECUTE --> E_ALL_FAIL
    E_ALL_FAIL -- 是 + retry < 2 --> E_RETRY
    E_RETRY --> ANALYZE
    E_ALL_FAIL -- 是 + retry >= 2 --> V_FAIL
    E_ALL_FAIL -- 否（部分成功） --> FORMAT

    %% rule 路径（直接到格式化）
    ANALYZE_RULE --> FORMAT

    %% 输出
    FORMAT --> END_NODE

    %% 样式
    classDef node fill:#e1f5fe,stroke:#0288d1
    classDef decision fill:#fff3e0,stroke:#f57c00
    classDef retry fill:#fce4ec,stroke:#d32f2f
    classDef io fill:#e8f5e9,stroke:#388e3c
    classDef intentNode fill:#e8eaf6,stroke:#283593
    classDef ruleNode fill:#fce4ec,stroke:#880e4f
    class ANALYZE,VALIDATE,EXECUTE,FORMAT node
    class V_OK,E_ALL_FAIL,ROUTE decision
    class V_RETRY,E_RETRY,V_FAIL retry
    class START,END_NODE,INIT io
    class INTENT intentNode
    class ANALYZE_RULE ruleNode
```

## 路由说明

| 节点 | 出口 | 条件 | 去向 |
|------|------|------|------|
| **intent_recognition** | `chat` | 用户闲聊/问候 | **format_reply** |
| | `chart` | 用户想看数据/图表 | **analyze** |
| | `rule` | 用户想了解规则函数 | **analyze_rule** |
| **validate** | 通过 | charts 校验合法 | **execute** |
| | 重试 | 校验失败 + `analyze_retry_count < 1` | **analyze** |
| | 失败 | 校验失败 + `analyze_retry_count >= 1` | **format_reply** |
| **execute** | 重试 | 全部 SQL 失败 + `execute_retry_count < 2` | **analyze** |
| | 完成 | 部分成功或重试耗尽 | **format_reply** |

## 重试机制

- **validate 重试**：最多 **1 次**，校验失败时携带 `validation_error` 喂给 LLM 修正
- **SQL 重试**：最多 **2 次**，全表查询失败时携带 `sql_error` 喂给 LLM 修正
- 重试仍失败 → 前端显示友好提示

## 新增模型

### IntentOutput（意图识别输出）
- `intent`: `"chat" | "chart" | "rule"`
- `reason`: 判断原因

### RuleRecommendation（规则函数推荐）
- `rule_name`: 规则名称
- `rule_type`: 规则类型
- `description`: 功能说明
- `priority`: 推荐优先级
