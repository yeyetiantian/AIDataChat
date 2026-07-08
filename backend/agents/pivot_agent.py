"""LangGraph AI 分析与图表配置 Agent

将用户自然语言转换为 PivotConfig 图表配置（Pivot API 代为执行查询）。
保留完整链路日志（每个节点的原始输入/输出）。

支持一次生成多种图表：如"各车型和各规则的报警次数"→2个图表。

数据流：analyze（LLM 解析）→ validate（校验/重试）→ execute（查数据）→ format_reply（日志+回复）
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from core.field_registry import get_schema_for_agent, get_fixed_field_names
from llm import get_auth_headers
from models import PivotConfig, PivotResponse

logger = logging.getLogger("pivot_agent")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Structured Output 模型
# ============================================================

class ChartItem(BaseModel):
    """单个图表配置"""
    title: str = Field("", description="图表标题说明")
    pivot_config: PivotConfig = Field(..., description="报表配置")
    chart_type: Literal["bar", "line", "area", "point", "pie", "radar"] = Field(
        "bar", description="图表类型"
    )


class AgentOutput(BaseModel):
    """LLM 结构化输出：聊天或图表（统一走 charts 列表）"""
    intent: Literal["chat", "chart"] = Field(description="chat=普通聊天, chart=图表分析")
    reply: str = Field(description="回复内容")
    # 单图表兼容字段（LLM 可能输出单图，analyze 节点统一转成 charts）
    # 多图表字段
    charts: list[ChartItem] = Field(default_factory=list, description="多图表（一次生成多个图表时使用）")
    suggestions: list[str] = Field(default_factory=list, description="建议用户追问的 3 个问题")


# ============================================================
# 全局缓存（单例）
# ============================================================

_llm: Optional[ChatOpenAI] = None
_structured_llm: Any = None
_schema_cache: Optional[str] = None
_base_system_prompt: Optional[str] = None


def _is_private_provider() -> bool:
    """判断是否使用私有 LLM"""
    return os.getenv("LLM_PROVIDER", "openai").strip().lower() == "private"


def _get_llm() -> ChatOpenAI:
    """获取 ChatOpenAI 实例（支持 openai / private 两种 provider）"""
    if _is_private_provider():
        # Private LLM：每次调用拿新 token，不缓存
        api_url = os.getenv("PRIVATE_LLM_API_URL")
        model = os.getenv("PRIVATE_LLM_MODEL", "qwen-27b")
        headers = get_auth_headers()
        return ChatOpenAI(
            model=model,
            temperature=0.1,
            api_key="sk-placeholder",
            base_url=api_url,
            default_headers=headers,
        )

    # OpenAI / 兼容接口：全局单例
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
    return _llm


def _get_structured_llm() -> Any:
    """结构化输出 LLM（绑定 AgentOutput 模型）

    DeepSeek API 暂不支持 response_format / function_calling 强制结构化，
    保留此方法做尝试，失败则回退到手动解析。
    """
    if _is_private_provider():
        # Private LLM：每次都创建（token 可能过期，且 function_calling 可能不支持）
        try:
            return _get_llm().with_structured_output(AgentOutput, method="function_calling")
        except Exception:
            logger.warning("Private LLM 不支持 StructuredOutput，将使用手动 JSON 解析")
            return None

    # OpenAI / 兼容接口：全局缓存
    global _structured_llm
    if _structured_llm is None:
        try:
            _structured_llm = _get_llm().with_structured_output(AgentOutput, method="function_calling")
        except Exception:
            logger.warning("StructuredOutput 初始化失败（DeepSeek API 兼容限制），将使用手动 JSON 解析")
            _structured_llm = None
    return _structured_llm


def _get_schema_text() -> str:
    """全局缓存的 Schema 文本"""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = get_schema_for_agent(top_signals=60)
    return _schema_cache


def _get_base_system_prompt() -> str:
    """只构建一次的 System Prompt 基础内容（不含对话上下文）"""
    global _base_system_prompt
    if _base_system_prompt is not None:
        return _base_system_prompt

    schema = _get_schema_text()
    _base_system_prompt = f"""你是数据分析助手，支持普通聊天和数据透视图表分析。

## 数据字段说明

{schema}

## 行为规则

### 1. 普通聊天模式
用户只是打招呼、问简单问题，直接回复即可。
suggestions 字段必须为空列表（无需生成追问）。

### 2. 图表分析模式
根据用户的自然语言意图，结合数据透视规则，生成 PivotConfig 图表配置（charts 列表），供 Pivot API 执行查询。

**默认：每个请求只生成一个图表。** 即使请求包含多个维度，也聚合到一个图表中。

**多图表例外**：只有用户明确说"分别展示"、"生成多个图表"这类明确表示要多个图表时，才使用多个图表。

所有图表配置统一使用 charts 数组，即使只生成一个图表也放在 charts 中。
每个图表包含 title、pivot_config、chart_type。

单图表示例（默认行为）：
{{"intent": "chart", "reply": "各车型的报警次数如下：", "charts": [
  {{ "title": "各车型报警次数", "pivot_config": {{ "filters": [{{"field": "vehicle", "op": "in", "value": ["VIN1", "VIN2"] }}], "axes": [{{"field": "vehicle_type", "alias": "车型"}}], "values": [{{"field": "alarm_time", "aggregation": "source", "alias": "报警次数"}}], "having": [], "limit": 1000 }}, "chart_type": "bar" }}
]}}

多图表示例（仅当用户明确要求时才使用）：
{{"intent": "chart", "reply": "好的，分别展示各车型和各规则的数据：", "charts": [
  {{ "title": "各车型报警次数", "pivot_config": {{ "filters": [], "axes": [{{"field": "vehicle_type", "alias": "车型"}}], "values": [{{"field": "alarm_time", "aggregation": "count", "alias": "报警次数"}}], "having": [], "limit": 100 }}, "chart_type": "bar" }},
  {{ "title": "各规则类型报警次数", "pivot_config": {{ "filters": [], "axes": [{{"field": "rule_type", "alias": "规则类型"}}], "values": [{{"field": "alarm_time", "aggregation": "count", "alias": "报警次数"}}], "having": [], "limit": 1000 }}, "chart_type": "bar" }}
]}}

**chart_type 规则**：
- 如果用户明确指定了图表类型（如"生成雷达图""改成饼图"），必须使用用户指定的类型，不要擅自更改
- 如果用户未指定图表类型，根据数据特征自动匹配合适的图表（见下方选择规则）

### 图表字段说明

**axes**（行维度，必填，至少 1 个）
- field: 字段名（必填）
- alias: 显示别名（必填，默认显示字段名）
- aggregation: source / day / week / month / year（仅时间字段可用，按 原值/天/周/月/年聚合）
- 示例：{{"field": "vehicle_type", "alias": "车型"}}、{{"field": "alarm_time", "aggregation": "month", "alias": "报警时间"}}

**legend**（列维度/图例，【图例默认不指定，除非用户明确指定某种图例】）
- field: 字段名（必填）
- alias: 显示别名（必填）

**values**（聚合值，必填，至少 1 个）
- field: 字段名（必填），支持固定字段和动态信号
- alias: 显示别名（必填，默认用字段名）
- aggregation: source / count / sum / avg / min / max
- 约束： 可用于任意字段；sum/avg/min/max 建议用于数值字段或动态信号列，默认使用source/count，用户有明确要求时再使用 sum/avg/min/max。

**filters**（筛选条件，可选）
- field: 字段名（必填）只能选择固定字段中的字段（不支持动态信号列）
- value: 必须是数组，如 ["VIN1", "VIN2"] / [4523] / ["2026-06-20 00:00:00", "2026-07-01 00:00:00"]；数值不要加引号;
- op: 只能在这里面选择【lt / gt / gte / lte / between / in】 (如果value是非时间的数组，op必须是 in，如果是时间范围，op必须使用 between)
- filter_type：筛选器类型（可选）
- 示例：{{"field": "vehicle_type", "op": "in", "value": ["SUV", "MPV"], "filter_type": ""}}/{{"field": "alarm_time", "op": "between", "value": ["2026-06-20 00:00:00", "2026-07-01 00:00:00"], "filter_type": ""}}

**having**（聚合后过滤，默认不填，除非用户明确要求）
- field: 聚合字段名
- op: 只能在这里面选择【lt / gt / gte / lte / between / in】
- value: 单个值（非数组）
- 示例：{{"field": "vehicle_type", "op": "gt", "value": 10}}

**order_by**（排序，默认不填，除非用户明确要求）
- field: 字段名（必填）
- dir: 只能在这里面选择【asc / desc】
- 示例：{{"field": "alarm_time", "dir": "desc"}}

**limit**（最大返回条数，可选）
- 整数，默认 1000，最大 10000
- 示例：1000

**chart_type**（图表类型）
- 可选值：bar / line / area / point / pie / radar
- 选择规则：类别对比 → bar（柱状图），时间趋势 → line（折线图），面积趋势 → area（面积图），占比分布 → pie（饼图），数据点分布 → point（散点图），多维指标对比 → radar（雷达图）

### 约束汇总
- axes 至少 1 个，values 至少 1 个
- 所有字段名（field）必须来自上面的数据字段列表，不能编造不存在的字段，如果你遇到不确定或不认识的字段名，一律归类为动态信号列，使用其原始列名即可。
- 对动态信号列（不在固定字段中的列名）做 source / count / sum / avg / min / max 聚合时，系统自动转换数值类型，直接使用列名即可"""
    return _base_system_prompt


# ---- Agent State ----
class AgentState(TypedDict):
    """Agent 状态"""
    user_message: str
    conversation_history: list[dict[str, str]]
    intent: Optional[str]
    # 全流程统一使用 charts 列表，废弃顶层单图字段
    charts: list[dict[str, Any]]          # [{pivot_config, chart_type, title, data, sql, vega_spec}]
    suggestions: list[str]
    reply: str
    error: Optional[str]
    analyze_retry_count: int              # 校验重试计数（最多 1 次）
    validation_error: Optional[str]       # 校验失败原因（重试时喂给 LLM）
    execute_retry_count: int              # SQL 执行失败重试计数（最多 2 次）
    sql_error: Optional[str]              # SQL 执行错误信息（重试时喂给 LLM）
    trace_log: list[dict[str, Any]]


def _snapshot(state: AgentState) -> dict:
    """对 state 做安全快照（去掉超大字段，用于日志）"""
    s = dict(state)
    s["trace_log"] = f"<{len(state.get('trace_log', []))} entries>"
    if s.get("charts"):
        s["charts"] = f"<{len(s['charts'])} charts>"
    if s.get("conversation_history"):
        s["conversation_history"] = f"<{len(s['conversation_history'])} msgs>"
    return s


def _save_trace_log(state: AgentState, session_id: str = None) -> str:
    """保存 Agent 链路日志到文件"""
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    charts = state.get("charts", []) or []
    data_rows = 0
    sql_snippets = []
    for ch in charts:
        d = ch.get("data", []) or []
        data_rows += len(d)
        sql_snippets.append(ch.get("sql", ""))

    log_entry = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "user_message": state.get("user_message", ""),
        "intent": state.get("intent"),
        "sql": sql_snippets,
        "data_rows": data_rows,
        "chart_count": len(charts),
        "reply": state.get("reply"),
        "suggestions": state.get("suggestions"),
        "error": state.get("error"),
        "validation_error": state.get("validation_error"),
        "sql_error": state.get("sql_error"),
        "analyze_retry_count": state.get("analyze_retry_count"),
        "execute_retry_count": state.get("execute_retry_count"),
        "trace": state.get("trace_log", []),
    }

    log_path = os.path.join(LOG_DIR, f"agent_{session_id}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
    return log_path


# ---- 数据标准化 ----

# 筛选器 op 合法值
_FILTER_VALID_OPS = {"lt", "gt", "gte", "lte", "between", "in"}

# 固定字段名缓存（模块级，第一次调用时初始化）
_fixed_field_names: set[str] | None = None


def _get_fixed_names() -> set[str]:
    global _fixed_field_names
    if _fixed_field_names is None:
        _fixed_field_names = get_fixed_field_names()
    return _fixed_field_names


def _deep_normalize_chart(chart: dict[str, Any]) -> dict[str, Any]:
    """深度标准化单个图表配置"""
    pc = chart.get("pivot_config")
    if not pc or not isinstance(pc, dict):
        return chart

    fixed_names = _get_fixed_names()

    # ---------- filters 处理 ----------
    filters = pc.get("filters")
    if isinstance(filters, list) and len(filters) > 0:
        cleaned: list[dict] = []
        for f in filters:
            if not isinstance(f, dict):
                continue
            # 校验 field：不在固定字段中的过滤掉
            if not f.get("field") or f["field"] not in fixed_names:
                continue
            # 确保 value 是数组
            val = f.get("value")
            if not isinstance(val, list):
                val = [val] if val is not None else []
            # 尝试将每个元素转为数字
            converted: list = []
            for v in val:
                if isinstance(v, str):
                    try:
                        if "." in v or v.isdigit():
                            converted.append(float(v) if "." in v else int(v))
                        else:
                            converted.append(v)
                    except (ValueError, TypeError):
                        converted.append(v)
                else:
                    converted.append(v)
            f["value"] = converted
            # 校验 op
            op = f.get("op", "in")
            if op not in _FILTER_VALID_OPS:
                op = "in"
            f["op"] = op
            cleaned.append(f)
        pc["filters"] = cleaned

    # ---------- legend 处理 ----------
    legend = pc.get("legend")
    values = pc.get("values", [])
    # 收集 values 中的 field（全局使用，供 legend 和 order_by 校验）
    value_fields: set[str] = set()
    if isinstance(values, list):
        for v in values:
            if isinstance(v, dict):
                if v.get("field"):
                    value_fields.add(v["field"])

    if isinstance(legend, list) and len(legend) > 0 and isinstance(values, list):
        # 过滤 legend：field 必须出现在固定字段中或 value 字段列表中
        pc["legend"] = [
            l for l in legend
            if isinstance(l, dict) and l.get("field")
            and (l["field"] in fixed_names or l["field"] in value_fields)
        ]

    # ---------- order_by 处理 ----------
    ob = pc.get("order_by", [])
    if isinstance(ob, list) and len(ob) > 0:
        pc["order_by"] = [
            o for o in ob
            if isinstance(o, dict) and o.get("field")
            and o["field"] in value_fields
        ]

    return chart


def _normalize_charts_from_output(response: AgentOutput) -> list[dict[str, Any]]:
    """将 AgentOutput 统一标准化为 state.charts 列表

    支持三种来源：
    1. response.charts（多图表）
    3. 空列表（chat 模式）
    """
    if response.charts:
        charts = [c.model_dump() for c in response.charts]
        return [_deep_normalize_chart(ch) for ch in charts]

    return []


# ---- JSON 解析辅助 ----

def _try_parse_json(text: str) -> dict | None:
    """尝试解析 JSON，自动处理 LLM 输出的双花括号"""
    if not text:
        return None
    # 先试原生解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 双花括号转单花括号
    cleaned = text.replace("{{", "{").replace("}}", "}")
    if cleaned != text:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
    return None

# ---- 校验逻辑 ----

def _validate_chart(chart: dict[str, Any]) -> str | None:
    """校验单个图表配置，返回错误信息或 None"""
    pc = chart.get("pivot_config")
    if not pc or not isinstance(pc, dict):
        return f"图表「{chart.get('title', '未命名')}」缺少 pivot_config"

    values = pc.get("values", [])
    if not isinstance(values, list) or len(values) == 0:
        return f"图表「{chart.get('title', '未命名')}」的 values 为空，必须至少指定一个聚合值"

    for i, v in enumerate(values):
        if not isinstance(v, dict):
            return f"图表「{chart.get('title', '未命名')}」values[{i}] 不是有效对象"
        if not v.get("field"):
            return f"图表「{chart.get('title', '未命名')}」values[{i}] 缺少 field 或 expr"

    axes = pc.get("axes", [])
    if not isinstance(axes, list) or len(axes) == 0:
        return f"图表「{chart.get('title', '未命名')}」的 axes 为空，必须至少指定一个维度字段"

    return None


def _validate_charts(charts: list[dict[str, Any]]) -> str | None:
    """校验整个 charts 列表，返回第一条错误或 None"""
    if not charts:
        return "未生成任何图表配置"

    for chart in charts:
        err = _validate_chart(chart)
        if err:
            return err
    return None


# ---- Agent Nodes ----

def analyze_node(state: AgentState) -> AgentState:
    """NL2SQL 分析节点：用 Structured Output 调用 LLM 生成配置"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "analyze_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    try:
        structured_llm = _get_structured_llm()

        # 合并所有 system 内容为一条（私有 LLM 如 Qwen 只允许一条 system 消息且在位置 0）
        system_parts = [_get_base_system_prompt()]

        if state.get("analyze_retry_count", 0) > 0 and state.get("validation_error"):
            system_parts.append(
                f"注意：上一次生成的配置在校验中未通过，请根据以下反馈修正：\n{state['validation_error']}\n请重新生成符合要求的配置。"
            )

        if state.get("execute_retry_count", 0) > 0 and state.get("sql_error"):
            system_parts.append(
                f"注意：上一次生成的配置在 SQL 查询时出错：\n{state['sql_error']}\n请检查字段名、值 ID 引用和列名是否正确，重新生成配置。"
            )

        # 先构建基础消息（不含 format instructions），供 structured_llm 使用
        base_system = "\n\n".join(system_parts)
        messages = [{"role": "system", "content": base_system}]
        history = [h for h in (state.get("conversation_history") or []) if h.get("role") != "system"]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": state["user_message"]})

        response: AgentOutput | None = None
        if structured_llm is not None:
            try:
                response = structured_llm.invoke(messages)
                trace.append({
                    "step": "llm_structured_output",
                    "timestamp": datetime.now().isoformat(),
                    "raw_output": response.model_dump_json()[:1000],
                })
            except Exception:
                logger.warning("StructuredOutput 调用失败，使用 PydanticOutputParser 兜底")
                response = None

        if response is None:
            # 兜底：PydanticOutputParser（LangChain 内置方案，兼容所有 LLM）
            parser = PydanticOutputParser(pydantic_object=AgentOutput)
            format_instructions = parser.get_format_instructions()

            # 将格式说明追加到 system prompt 中
            messages[0] = {"role": "system", "content": f"{base_system}\n\n## 输出格式\n{format_instructions}"}

            raw_llm = _get_llm()
            raw_resp = raw_llm.invoke(messages)
            raw_content = raw_resp.content.strip()

            trace.append({
                "step": "llm_pydantic_parser",
                "timestamp": datetime.now().isoformat(),
                "raw_output": raw_content[:1000],
            })

            try:
                response = parser.parse(raw_content)
            except Exception as parse_err:
                logger.error("PydanticOutputParser 解析失败: %s", parse_err)
                # 最后尝试带标准化的手动解析
                result = _try_parse_json(raw_content)
                response = AgentOutput(
                    intent=result.get("intent", "chart"),
                    reply=result.get("reply", ""),
                    charts=result.get("charts", []),
                    suggestions=result.get("suggestions", []),
                )

        if response.intent == "chat":
            state["intent"] = "chat"
            state["reply"] = response.reply
            state["suggestions"] = []
            state["charts"] = []
            state["error"] = None
            trace.append({"step": "analyze_complete", "intent": "chat"})
        else:
            state["intent"] = "chart"
            state["suggestions"] = response.suggestions or []
            state["reply"] = response.reply
            state["error"] = None
            state["charts"] = _normalize_charts_from_output(response)
            trace.append({
                "step": "analyze_complete",
                "intent": "chart",
                "chart_count": len(state["charts"]),
            })

    except Exception as e:
        logger.error("Agent 分析失败: %s", e, exc_info=True)
        state["error"] = str(e)
        state["reply"] = f"分析时出错：{e}"
        state["charts"] = []
        trace.append({"step": "analyze_error", "error": str(e)})

    trace.append({
        "step": "analyze_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


def validate_config_node(state: AgentState) -> AgentState:
    """校验节点：校验 charts 配置合法性，不通过则回流 analyze 重试（最多 1 次）"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "validate_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    if state.get("intent") == "chat" or not state.get("charts"):
        # chat 模式或空图表 → 直接通过
        state["validation_error"] = None
        trace.append({"step": "validate_skip", "reason": "no_charts"})
        state["trace_log"] = trace
        return state

    err = _validate_charts(state["charts"])
    if err is None:
        # 校验通过
        state["validation_error"] = None
        trace.append({"step": "validate_pass"})
    else:
        retry_count = state.get("analyze_retry_count", 0)
        state["validation_error"] = err

        if retry_count < 1:
            # 未超过重试上限 → 标记重试
            state["analyze_retry_count"] = retry_count + 1
            state["reply"] = f"配置校验未通过（第 1 次重试）：{err}"
            trace.append({
                "step": "validate_retry",
                "retry_count": state["analyze_retry_count"],
                "error": err,
            })
        else:
            # 重试耗尽 → 报错，清除标记避免循环
            state["validation_error"] = None
            state["charts"] = []
            state["error"] = (state.get("error") or "") + f" 配置校验失败（已重试）：{err}"
            if not state.get("reply"):
                state["reply"] = f"配置校验多次失败：{err}，请尝试换个问法。"
            trace.append({
                "step": "validate_fail",
                "error": err,
            })

    trace.append({
        "step": "validate_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


# ---- Pivot 查询：HTTP 调用 ----

_PIVOT_API_URL: str | None = None


def _get_pivot_api_url() -> str:
    """获取 Pivot API 地址（环境变量 PIVOT_API_URL，默认 http://127.0.0.1:8000/api/pivot）"""
    global _PIVOT_API_URL
    if _PIVOT_API_URL is None:
        _PIVOT_API_URL = os.getenv("PIVOT_API_URL", "http://127.0.0.1:8000/api/pivot").rstrip("/")
    return _PIVOT_API_URL


def _pivot_via_http(config: PivotConfig) -> dict:
    """通过 HTTP 调用 /api/pivot 执行查询，返回与 execute_pivot 相同的数据结构"""
    import requests

    url = _get_pivot_api_url()
    payload = config.model_dump()

    # 如果是私有 LLM，复用 auth headers 传给 pivot API
    headers = {"Content-Type": "application/json"}

    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        detail = resp.json().get("detail", resp.text) if resp.text else resp.reason
        raise RuntimeError(f"Pivot 查询失败: {detail}")

    result = resp.json()
    return {
        "data": result.get("data", []),
        "columns": result.get("columns", []),
        "total": result.get("total", 0),
        "vega_spec": result.get("vega_spec", {}),
        "config": result.get("config"),
        "sql": result.get("sql"),
        "execution_time_ms": result.get("execution_time_ms", 0),
    }


def execute_node(state: AgentState) -> AgentState:
    """执行节点：遍历 state.charts 逐个查询数据，完整暴露 SQL"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "execute_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    if state.get("intent") == "chat":
        trace.append({"step": "execute_skip", "reason": "chat_intent"})
        state["trace_log"] = trace
        return state

    charts = state.get("charts", []) or []
    errors: list[str] = []
    for chart in charts:
        pc_dict = chart.get("pivot_config") or chart.get("config")
        ct = chart.get("chart_type", "bar")
        if not pc_dict:
            chart["error"] = "缺少 pivot_config"
            errors.append("缺少 pivot_config")
            continue

        pc_dict["chart_type"] = ct
        try:
            cfg = PivotConfig(**pc_dict)
            res = _pivot_via_http(cfg)
            chart["data"] = res.get("data", [])
            chart["vega_spec"] = res.get("vega_spec", {})
            chart["sql"] = res.get("sql")
        except Exception as e2:
            logger.error("图表执行失败: %s, config=%s", e2, pc_dict)
            chart["error"] = str(e2)
            chart.setdefault("data", [])
            chart.setdefault("sql", "")
            errors.append(str(e2))

    # 判断是否需要重试：所有图表都失败，且未超重试上限
    all_failed = len(errors) > 0 and len(errors) == len(charts)
    retry_count = state.get("execute_retry_count", 0)

    if all_failed and retry_count < 2:
        state["execute_retry_count"] = retry_count + 1
        state["sql_error"] = f"SQL 查询失败（第 {retry_count + 1} 次重试）：{errors[0]}"
        trace.append({
            "step": "execute_retry",
            "retry_count": state["execute_retry_count"],
            "errors": errors,
        })
    elif all_failed:
        state["error"] = (state.get("error") or "") + f" SQL 执行多次失败：{errors[0]}"
        state["sql_error"] = None
        trace.append({
            "step": "execute_fail",
            "errors": errors,
        })
    else:
        # 至少有一个成功
        state["sql_error"] = None
        trace.append({"step": "execute_success", "chart_count": len(charts)})

    trace.append({
        "step": "execute_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


def format_reply_node(state: AgentState) -> AgentState:
    """格式化回复节点：构造最终回复并保存日志"""
    trace = state.get("trace_log", [])
    trace.append({
        "step": "format_reply_start",
        "timestamp": datetime.now().isoformat(),
        "input_snapshot": _snapshot(state),
    })

    charts = state.get("charts", []) or []
    total_rows = sum(len(ch.get("data", []) or []) for ch in charts)
    all_errors = [ch.get("error") for ch in charts if ch.get("error")]

    if total_rows > 0:
        state["reply"] += f"\n\n共查询到 {total_rows} 条结果。"
    elif all_errors and len(all_errors) == len(charts):
        # 全部图表都失败时，回复中加入友好提示，不暴露原始技术错误
        state["reply"] = (state.get("reply") or "") + "\n\n图表查询失败，请尝试换个方式描述分析需求。"
        if not state.get("error"):
            state["error"] = "; ".join(all_errors[:3])

    log_path = _save_trace_log(state)
    trace.append({"step": "log_saved", "path": log_path})

    trace.append({
        "step": "format_reply_end",
        "timestamp": datetime.now().isoformat(),
        "output_snapshot": _snapshot(state),
    })
    state["trace_log"] = trace
    return state


def build_agent() -> Any:
    """构建 LangGraph Agent（analyze → validate → execute → format_reply）

    validate 条件分支：
    - "ok"      → execute（校验通过）
    - "retry"   → analyze（校验失败且未超重试上限）
    - "fail"    → format_reply（校验失败且重试耗尽）
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("analyze", analyze_node)
    workflow.add_node("validate", validate_config_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("format_reply", format_reply_node)

    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "validate")

    # validate 条件路由
    def _route_after_validate(state: AgentState) -> str:
        if state.get("intent") == "chat":
            return "format_reply"
        if state.get("validation_error") and state.get("analyze_retry_count", 0) > 0:
            # 有校验错误且已标记重试 → 回流 analyze
            return "analyze"
        if state.get("validation_error"):
            # 校验失败且重试耗尽 → 结束
            return "format_reply"
        if state.get("charts"):
            return "execute"
        return "format_reply"

    workflow.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "analyze": "analyze",
            "execute": "execute",
            "format_reply": "format_reply",
        },
    )

    # execute 条件路由：执行失败直接走 format_reply，不重试大模型
    def _route_after_execute(state: AgentState) -> str:
        return "format_reply"

    workflow.add_conditional_edges(
        "execute",
        _route_after_execute,
        {
            "analyze": "analyze",
            "format_reply": "format_reply",
        },
    )
    workflow.add_edge("format_reply", END)

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app


# 全局 Agent 实例
_agent = None


def get_agent() -> Any:
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


async def process_chat(message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """处理聊天请求"""
    import uuid
    start = time.time()

    # 检查认证配置
    if _is_private_provider():
        if not os.getenv("PRIVATE_LLM_CLIENT_ID") or not os.getenv("PRIVATE_LLM_TOKEN_URL"):
            return {
                "reply": "私有 LLM 需要配置 PRIVATE_LLM_CLIENT_ID / PRIVATE_LLM_TOKEN_URL 环境变量",
                "charts": [],
                "suggestions": [],
                "execution_time_ms": 0,
            }
    elif not os.getenv("OPENAI_API_KEY"):
        return {
            "reply": "AI 对话需要配置 OPENAI_API_KEY 环境变量，请先在 .env 文件中设置。",
            "charts": [],
            "suggestions": [],
            "execution_time_ms": 0,
        }

    agent = get_agent()
    thread_id = str(uuid.uuid4())

    state: AgentState = {
        "user_message": message,
        "conversation_history": history or [],
        "intent": None,
        "charts": [],
        "suggestions": [],
        "reply": "",
        "error": None,
        "analyze_retry_count": 0,
        "validation_error": None,
        "execute_retry_count": 0,
        "sql_error": None,
        "trace_log": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(state, config)

    elapsed = (time.time() - start) * 1000

    return {
        "reply": result.get("reply", ""),
        "charts": result.get("charts", []) or [],
        "suggestions": result.get("suggestions", []),
        "execution_time_ms": round(elapsed, 2),
    }
