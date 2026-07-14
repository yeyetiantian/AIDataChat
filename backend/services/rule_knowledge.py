"""规则推荐所需的任务、规则、函数、信号和报警证据检索。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from core.chat_db import (
    get_task,
    list_freeze_functions,
    list_rule_signal_stats,
    list_task_rules,
    search_rules,
    search_tasks,
)
from models import AlarmSummary, EntityReference, TaskReference


def _as_signal_names(raw: Any) -> list[str]:
    """兼容历史规则字段中的 JSON、数组和逗号分隔信号名。"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return _as_signal_names(decoded)
        if isinstance(decoded, dict):
            values: list[str] = []
            for value in decoded.values():
                values.extend(_as_signal_names(value))
            return values
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return [part.strip(" []{}\"'") for part in re.split(r"[,;|\n]", text) if part.strip(" []{}\"'")]


def _find_explicit_task_id(message: str) -> int | None:
    matched = re.search(r"(?:TASK[_ ]?ID|任务(?:编号|ID)?)[：:#\s]*(\d+)", message, re.IGNORECASE)
    return int(matched.group(1)) if matched else None


def _select_task(message: str, task_id: int | None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if task_id is not None:
        return get_task(task_id), []
    explicit_id = _find_explicit_task_id(message)
    if explicit_id is not None:
        return get_task(explicit_id), []

    # 精确命中任务名称时直接选择；否则只把候选交给调用方用于澄清。
    candidates = search_tasks(message.strip(), limit=5) if message.strip() else []
    exact = [item for item in candidates if item.get("TASK_NAME") and item["TASK_NAME"] in message]
    if len(exact) == 1:
        return exact[0], candidates
    return None, candidates


def _find_functions(message: str, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    functions = list_freeze_functions(deleted=False)
    if not functions:
        return []
    query = " ".join([message] + [str(r.get("RULE_NAME", "")) for r in rules]).lower()
    matched = []
    for item in functions:
        terms = [str(item.get(key, "")).strip().lower() for key in ("name", "func_type")]
        if any(term and term in query for term in terms):
            matched.append(item)
    # 找不到关键词时仅提供有限候选，避免把整个函数库塞入 prompt。
    return (matched or functions)[:20]


@dataclass
class RuleKnowledge:
    task: TaskReference = field(default_factory=TaskReference)
    task_candidates: list[TaskReference] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)
    alarm_summary: AlarmSummary = field(default_factory=AlarmSummary)
    citations: list[EntityReference] = field(default_factory=list)
    data_issues: list[str] = field(default_factory=list)

    @property
    def resolved_task_id(self) -> int | None:
        return self.task.id

    def prompt_context(self) -> str:
        """向 LLM 注入受限、可引用的事实，不包含无关全库数据。"""
        lines = ["## 已检索的业务事实（只能引用此处存在的实体）"]
        if self.task.id is not None:
            lines.append(f"任务：TASK_ID={self.task.id}，名称={self.task.name}")
        elif self.task_candidates:
            choices = "；".join(f"{c.name}(TASK_ID={c.id})" for c in self.task_candidates)
            lines.append(f"任务尚未确认。候选任务：{choices}")
        else:
            lines.append("任务尚未确认，且未检索到可用候选。")

        lines.append("\n### 当前/相关规则")
        if self.rules:
            for rule in self.rules[:30]:
                lines.append(
                    "- RULE_ID={id}; 名称={name}; 描述={desc}; 开始={start}; 判断={judge}; 结束={end}; 信号={signals}".format(
                        id=rule.get("TASK_RULE_ID", ""), name=rule.get("RULE_NAME", ""),
                        desc=rule.get("RULE_DESCRIPTION", ""),
                        start=rule.get("START_EXPRESSION_CONVERT") or rule.get("START_EXPRESSION", ""),
                        judge=rule.get("JUDGE_EXPRESSION_CONVERT") or rule.get("JUDGE_EXPRESSION", ""),
                        end=rule.get("END_EXPRESSION_CONVERT") or rule.get("END_EXPRESSION", ""),
                        signals=rule.get("RULE_SIGNALS", ""),
                    )
                )
        else:
            lines.append("- 未检索到规则")

        lines.append("\n### 可用函数")
        if self.functions:
            for func in self.functions:
                lines.append(
                    f"- FUNC_ID={func['id']}; 名称={func['name']}; 参数={func.get('params', '')}; 返回={func.get('returns', '')}; 上下文={func.get('context', '')}"
                )
        else:
            lines.append("- 函数库为空或不可用；不要编造函数。")

        lines.append("\n### 可用信号与报警统计")
        if self.signals:
            for signal in self.signals[:80]:
                lines.append(
                    f"- 信号={signal['signal_name']}; 关联规则={signal.get('rule_ids', [])}; 报警数={signal.get('alarm_count', 0)}; 数据状态={signal.get('data_status', 'unavailable')}"
                )
        else:
            lines.append("- 未检索到信号统计；不要将其解释为没有报警。")
        lines.append(
            f"报警统计：状态={self.alarm_summary.source_status}；报警数={self.alarm_summary.alarm_count}；样本数={self.alarm_summary.sample_count}；更新时间={self.alarm_summary.updated_at or '未知'}"
        )
        if self.data_issues:
            lines.append("\n### 数据限制\n- " + "\n- ".join(self.data_issues))
        return "\n".join(lines)


def build_rule_knowledge(message: str, task_id: int | None = None) -> RuleKnowledge:
    """检索规则推荐上下文。数据源失败时显式降级，绝不伪造空数据。"""
    knowledge = RuleKnowledge()
    try:
        task, candidates = _select_task(message, task_id)
    except Exception as exc:
        knowledge.data_issues.append(f"任务元数据不可用：{exc}")
        return knowledge

    knowledge.task_candidates = [
        TaskReference(id=item.get("TASK_ID"), name=item.get("TASK_NAME", "")) for item in candidates
    ]
    if task:
        knowledge.task = TaskReference(id=task.get("TASK_ID"), name=task.get("TASK_NAME", ""))
        knowledge.citations.append(EntityReference(type="task", id=str(knowledge.task.id), label=knowledge.task.name))

    try:
        knowledge.rules = list_task_rules(knowledge.task.id) if knowledge.task.id is not None else search_rules(message, limit=20)
    except Exception as exc:
        knowledge.data_issues.append(f"规则元数据不可用：{exc}")

    for rule in knowledge.rules:
        knowledge.citations.append(EntityReference(
            type="existing_rule", id=str(rule.get("TASK_RULE_ID", "")), label=rule.get("RULE_NAME", ""),
            detail=rule.get("RULE_DESCRIPTION", ""),
        ))

    try:
        knowledge.functions = _find_functions(message, knowledge.rules)
    except Exception as exc:
        knowledge.data_issues.append(f"函数库不可用：{exc}")
    for func in knowledge.functions:
        knowledge.citations.append(EntityReference(type="function", id=str(func["id"]), label=func["name"], detail=func.get("description", "")))

    try:
        signal_rows = list_rule_signal_stats(knowledge.task.id) if knowledge.task.id is not None else []
        knowledge.signals = signal_rows
        if signal_rows:
            total_alarms = sum(int(row.get("alarm_count") or 0) for row in signal_rows)
            total_samples = sum(int(row.get("sample_count") or 0) for row in signal_rows)
            updated = max((row.get("updated_at") or "" for row in signal_rows), default="") or None
            status = "available" if any(row.get("data_status") == "available" for row in signal_rows) else "no_data"
            knowledge.alarm_summary = AlarmSummary(
                alarm_count=total_alarms, sample_count=total_samples, source_status=status, updated_at=updated,
            )
            for signal in signal_rows:
                knowledge.citations.append(EntityReference(
                    type="signal", id=signal["signal_name"], label=signal["signal_name"],
                    detail=f"关联规则: {signal.get('rule_ids', [])}; 报警数: {signal.get('alarm_count', 0)}",
                ))
        else:
            knowledge.alarm_summary = AlarmSummary(source_status="no_data")
            knowledge.data_issues.append("当前任务没有可用的信号/报警统计，无法据此判断报警表现。")
    except Exception as exc:
        knowledge.alarm_summary = AlarmSummary(source_status="unavailable")
        knowledge.data_issues.append(f"信号/报警统计不可用：{exc}")

    return knowledge
