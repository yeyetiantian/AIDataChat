# Agent 流程图

```mermaid
flowchart TD
    START(["用户输入 message + history"])
    
    subgraph process_chat["process_chat()"]
        INIT[初始化 AgentState]
    end

    subgraph LangGraph["LangGraph Agent"]
        ANALYZE[analyze_node<br/>LLM 结构化输出 / 手动 JSON 解析<br/>→ intent + charts]
        VALIDATE[validate_config_node<br/>校验 pivot_config 合法性]
        EXECUTE[execute_node<br/>遍历 charts 执行 SQL 查询]
        FORMAT[format_reply_node<br/>格式化回复 + 保存日志]
    end

    subgraph retry_validate["校验重试路径"]
        V_OK{"校验通过？"}
        V_RETRY["analyze_retry_count += 1"]
        V_FAIL["标记验证失败"]
    end

    subgraph retry_execute["SQL 重试路径"]
        E_ALL_FAIL{"所有图表<br/>都失败？"}
        E_RETRY["execute_retry_count += 1<br/>设置 sql_error"]
        E_PARTIAL["部分成功，继续"]
    end

    subgraph llm_fallback["LLM 调用"]
        STRUCT[with_structured_output<br/>返回 AgentOutput]
        MANUAL[手动 JSON 解析<br/>_try_parse_json + _extract_json_fragment<br/>+ _normalize_pivot]
    end

    subgraph output["输出"]
        END_NODE(["返回 charts + reply + suggestions"])
    end

    %% 主流程
    START --> INIT
    INIT --> ANALYZE

    %% analyze_node 内部
    ANALYZE --> STRUCT
    STRUCT -- 失败 --> MANUAL
    STRUCT -- 成功 --> PARSE_OK
    MANUAL --> PARSE_OK["生成 AgentOutput"]
    PARSE_OK --> ANALYZE_DONE{"intent?"}
    ANALYZE_DONE -- chart --> CHARTS["charts + pivot_config"]
    ANALYZE_DONE -- chat --> CHAT["reply only"]
    CHAT --> VALIDATE
    CHARTS --> VALIDATE

    %% validate 路由
    VALIDATE --> V_OK
    V_OK -- 通过 --> EXECUTE
    V_OK -- 失败 + retry_count < 1 --> V_RETRY
    V_RETRY --> ANALYZE
    V_OK -- 失败 + retry >= 1 --> V_FAIL
    V_FAIL --> FORMAT

    %% execute 路由
    EXECUTE --> E_ALL_FAIL
    E_ALL_FAIL -- 是 + retry_count < 2 --> E_RETRY
    E_RETRY --> ANALYZE
    E_ALL_FAIL -- 是 + retry >= 2 --> V_FAIL
    E_ALL_FAIL -- 否（至少一个成功） --> E_PARTIAL
    E_PARTIAL --> FORMAT

    %% format → 结束
    FORMAT --> END_NODE

    %% 样式
    classDef node fill:#e1f5fe,stroke:#0288d1
    classDef decision fill:#fff3e0,stroke:#f57c00
    classDef retry fill:#fce4ec,stroke:#d32f2f
    classDef io fill:#e8f5e9,stroke:#388e3c
    class ANALYZE,VALIDATE,EXECUTE,FORMAT node
    class V_OK,E_ALL_FAIL,ANALYZE_DONE decision
    class V_RETRY,E_RETRY,V_FAIL retry
    class START,END_NODE,INIT io
```

## 路由说明

| 节点 | 出口 | 条件 | 去向 |
|------|------|------|------|
| **analyze** | → | 固定边 | **validate** |
| **validate** | `ok` | 校验通过 | **execute** |
| | `retry` | 校验失败 + `analyze_retry_count < 1` | **analyze**（重试） |
| | `fail` | 校验失败 + `analyze_retry_count >= 1` | **format_reply**（报错） |
| | `chat` | intent == chat（非图表请求） | **format_reply**（直接回复） |
| **execute** | `analyze` | 所有图表 SQL 失败 + `execute_retry_count < 2` | **analyze**（重试 + sql_error 反馈） |
| | `format_reply` | SQL 执行成功或重试耗尽 | **format_reply** |
| **format_reply** | → | 固定边 | **END** |

## 重试机制

- **validate 重试**：最多 **1 次**，校验失败时携带 `validation_error` 喂给 LLM 修正
- **SQL 重试**：最多 **2 次**，全表查询失败时携带 `sql_error`（含 SQL 错误原文）喂给 LLM 修正
- 重试仍失败 → 前端显示友好提示"图表生成失败，请尝试重新描述分析需求"
