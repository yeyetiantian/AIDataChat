"""LLM 工具模块 — 集中管理 LLM 初始化 & 结构化输出 & JSON 解析 & Trace 日志

所有 Agent 共享同一组 LLM 实例，避免重复创建和重复代码。
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger("llm_utils")

_TEMPERATURE = 0.1


# ============================================================
# Provider 判断
# ============================================================

def is_private_provider() -> bool:
    """判断是否使用私有 LLM"""
    return os.getenv("LLM_PROVIDER", "openai").strip().lower() == "private"


def check_llm_config() -> str | None:
    """检查 LLM 配置是否完整，不完整则返回错误提示"""
    if is_private_provider():
        if not os.getenv("PRIVATE_LLM_CLIENT_ID") or not os.getenv("PRIVATE_LLM_TOKEN_URL"):
            return "私有 LLM 需要配置 PRIVATE_LLM_CLIENT_ID / PRIVATE_LLM_TOKEN_URL 环境变量"
    elif not os.getenv("OPENAI_API_KEY"):
        return "AI 对话需要配置 OPENAI_API_KEY 环境变量，请先在 .env 文件中设置。"
    return None


# ============================================================
# 全局 LLM 缓存（进程级别）
# ============================================================

_llm_instance: Any = None
_structured_llm_cache: dict[str, Any] = {}


def get_llm() -> Any:
    """获取 ChatOpenAI 实例（线程安全，支持 openai / private 两种 provider）"""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    err = check_llm_config()
    if err:
        raise RuntimeError(err)

    from langchain_openai import ChatOpenAI

    if is_private_provider():
        api_url = os.getenv("PRIVATE_LLM_API_URL")
        model = os.getenv("PRIVATE_LLM_MODEL", "qwen-27b")
        from llm import get_auth_headers
        headers = get_auth_headers()
        _llm_instance = ChatOpenAI(
            model=model, temperature=_TEMPERATURE, api_key="sk-placeholder",
            base_url=api_url, default_headers=headers,
        )
    else:
        _llm_instance = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=_TEMPERATURE,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
    return _llm_instance


# ============================================================
# 结构化输出
# ============================================================

def get_structured_llm(output_type: type[BaseModel]) -> Any | None:
    """获取 with_structured_output 包装后的 LLM

    使用完整模块路径作为缓存 key，避免不同 Agent 中同名 Pydantic 模型（如 AgentOutput）互相冲突。
    返回 None 表示当前环境不支持，调用方应兜底使用 PydanticOutputParser。
    """
    # 用模块完全限定名做 key，避免 chart_agent.AgentOutput 和 rule_agent.AgentOutput 冲突
    type_name = f"{output_type.__module__}.{output_type.__qualname__}"
    if type_name not in _structured_llm_cache:
        try:
            llm = get_llm()
            _structured_llm_cache[type_name] = llm.with_structured_output(
                output_type, method="function_calling"
            )
        except Exception:
            logger.warning("StructuredOutput 不支持 %s，将使用手动解析", type_name)
            _structured_llm_cache[type_name] = None
    return _structured_llm_cache[type_name]


def call_structured(
    output_type: type[BaseModel],
    messages: list[dict],
) -> BaseModel | None:
    """调用结构化输出，失败返回 None"""
    structured_llm = get_structured_llm(output_type)
    if structured_llm is not None:
        try:
            return structured_llm.invoke(messages)
        except Exception as e:
            logger.warning("StructuredOutput 调用 %s 失败: %s", output_type.__name__, e)
    return None


def call_llm_text(messages: list[dict]) -> str:
    """调用 LLM 返回纯文本"""
    llm = get_llm()
    resp = llm.invoke(messages)
    return resp.content.strip() if hasattr(resp, 'content') else str(resp)


# ============================================================
# JSON 解析辅助
# ============================================================

def try_parse_json(text: str) -> dict | None:
    """尝试解析 JSON，自动处理 LLM 输出的 Markdown 代码块包裹和双花括号"""
    if not text:
        return None

    # 去掉 Markdown 代码块包裹（```json ... ```）
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.find("\n")
        if first_nl != -1:
            cleaned = cleaned[first_nl:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 处理 LLM 转义产生的双花括号
    double_braced = cleaned.replace("{{", "{").replace("}}", "}")
    if double_braced != cleaned:
        try:
            return json.loads(double_braced)
        except json.JSONDecodeError:
            pass
    return None


# ============================================================
# Trace 日志
# ============================================================

LOG_DIR: str | None = None


def _get_log_dir() -> str:
    global LOG_DIR
    if LOG_DIR is None:
        LOG_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "agent_logs",
        )
        os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_DIR


# ============================================================
# Trace 采集器 — 记录 Agent 各节点完整输入/输出
# ============================================================

import uuid
import json as json_lib


class SpanNode:
    """单个 Span 节点，构成树形结构"""
    __slots__ = (
        "span_id", "name", "node_type", "status",
        "start_time", "end_time", "duration_ms",
        "input", "output", "error", "messages",
        "tokens", "children", "_parent",
    )

    def __init__(
        self,
        name: str,
        node_type: str = "chain",
        input: Any = None,
        parent: "SpanNode | None" = None,
    ):
        self.span_id = uuid.uuid4().hex[:12]
        self.name = name
        self.node_type = node_type  # agent / llm / chain / tool
        self.status = "in_progress"
        self.start_time = datetime.now().isoformat(timespec="milliseconds")
        self.end_time: str | None = None
        self.duration_ms: float | None = None
        self.input = input
        self.output: Any = None
        self.error: str | None = None
        self.messages: list[dict] | None = None  # LLM 的消息记录
        self.tokens: dict | None = None  # {input, output}
        self.children: list["SpanNode"] = []
        self._parent = parent

    def finish(self, output: Any = None, error: str | None = None):
        self.end_time = datetime.now().isoformat(timespec="milliseconds")
        self.status = "success" if error is None else "error"
        self.output = output
        self.error = error
        if self.start_time and self.end_time:
            from datetime import datetime as dt2
            fmt = "%Y-%m-%dT%H:%M:%S.%f"
            try:
                s = dt2.strptime(self.start_time[:23], fmt)
                e = dt2.strptime(self.end_time[:23], fmt)
                self.duration_ms = round((e - s).total_seconds() * 1000, 1)
            except Exception:
                self.duration_ms = 0

    def add_child(self, name: str, node_type: str = "chain", input: Any = None) -> "SpanNode":
        child = SpanNode(name, node_type, input, parent=self)
        self.children.append(child)
        return child

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.span_id,
            "name": self.name,
            "type": self.node_type,
            "status": self.status,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "duration": f"{self.duration_ms}ms" if self.duration_ms is not None else None,
            "durationMs": self.duration_ms,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "messages": self.messages,
            "tokens": self.tokens,
            "children": [c.to_dict() for c in self.children],
        }
        return d

    def to_json(self) -> str:
        return json_lib.dumps(self.to_dict(), ensure_ascii=False, default=str)

class TraceCollector:
    """全链路 Trace 采集器

    用法：
      tc = TraceCollector("sess-001", "用户消息")
      root = tc.root
      span = root.add_child("analyze", "llm", input={...})
      span.finish(output={...})
      tc.session_id = ...
      tc.save_to_db()  # 最后调用
    """

    def __init__(self, session_id: str, request_message: str, agent_name: str = "chart_agent"):
        self.trace_id = uuid.uuid4().hex[:12]
        self.session_id = session_id
        self.request_message = request_message
        self.agent_name = agent_name
        self.root = SpanNode(
            name=f"Agent Executor ({agent_name})",
            node_type="agent",
            input={"message": request_message},
        )

    def save_to_db(self):
        """保存完整 trace 到本地 JSON 文件 (agent_logs/trace_{trace_id}.json)"""
        root_dict = self.root.to_dict()
        status = "error" if self.root.status == "error" else "success"

        log_entry = {
            "id": self.trace_id,
            "session_id": self.session_id or "",
            "request_message": self.request_message,
            "agent_name": self.agent_name,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "root_span": root_dict,
        }

        log_path = os.path.join(_get_log_dir(), f"trace_{self.trace_id}.json")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning("保存 trace 到本地文件失败: %s", e)


def save_trace_log(
    agent_name: str,
    state: dict[str, Any],
    extra: Optional[dict[str, Any]] = None,
    session_id: str | None = None,
) -> str:
    """保存 Agent 执行 trace 日志到 agent_logs/ 目录

    不再依赖 state['trace_log']（已废弃），改为从 TraceCollector 获取完整 span 树。
    若 state 中有 trace_collector，则存储完整的 root_span_json。

    Args:
        agent_name: agent 名称（chart_agent / rule_agent / chat_agent）
        state: agent state dict
        extra: 额外字段（如 data_rows 等）
        session_id: 日志文件名标识

    Returns:
        日志文件路径
    """
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # 优先从 TraceCollector 取完整 trace 树
    tc: TraceCollector | None = state.get("trace_collector")
    trace_data = tc.root.to_dict() if tc and tc.root else None

    log_entry: dict[str, Any] = {
        "agent": agent_name,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "user_message": state.get("user_message", ""),
        "reply": state.get("reply"),
        "error": state.get("error"),
        "trace": trace_data,
    }
    if extra:
        log_entry.update(extra)

    log_path = os.path.join(_get_log_dir(), f"{agent_name}_{session_id}.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2, default=str)
    return log_path
