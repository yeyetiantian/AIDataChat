"""规则推荐的确定性校验。"""

from __future__ import annotations

from models import LogicNode, RecommendationValidation, RuleConfigRecommendation, ValidationIssue
from services.rule_knowledge import RuleKnowledge


class RuleRecommendationValidator:
    def __init__(self, knowledge: RuleKnowledge):
        self.knowledge = knowledge
        self.function_ids = {item["id"] for item in knowledge.functions}
        self.function_names = {item["name"] for item in knowledge.functions}
        self.signal_names = {item["signal_name"] for item in knowledge.signals}
        for rule in knowledge.rules:
            for key in ("RULE_SIGNALS", "OTHER_SIGNALS"):
                raw = rule.get(key)
                if raw:
                    self.signal_names.update(str(raw).replace(";", ",").split(","))
        self.signal_names = {name.strip(" []{}\"'") for name in self.signal_names if name.strip(" []{}\"'")}

    def _walk_logic(self, node: LogicNode | None, path: str, issues: list[ValidationIssue], depth: int = 0) -> None:
        if node is None:
            return
        if depth > 6:
            issues.append(ValidationIssue(code="logic_too_deep", message="逻辑树最多支持 6 层嵌套", path=path))
            return
        if node.operator == "LEAF":
            if node.function is None or not (node.function.function_id or node.function.function_name):
                issues.append(ValidationIssue(code="missing_function", message="叶子条件必须引用一个函数", path=path))
                return
            if node.function.function_id is not None and node.function.function_id not in self.function_ids:
                issues.append(ValidationIssue(code="unknown_function", message=f"函数 ID {node.function.function_id} 不在当前函数库中", path=path))
            elif node.function.function_name and node.function.function_name not in self.function_names:
                issues.append(ValidationIssue(code="unknown_function", message=f"函数 {node.function.function_name} 不在当前函数库中", path=path))
            return
        if node.function is not None:
            issues.append(ValidationIssue(code="invalid_logic_node", message="组合逻辑节点不能直接配置函数", path=path))
        min_children = 1 if node.operator == "NOT" else 2
        if len(node.children) < min_children:
            issues.append(ValidationIssue(code="missing_logic_children", message=f"{node.operator} 至少需要 {min_children} 个子条件", path=path))
        for index, child in enumerate(node.children):
            self._walk_logic(child, f"{path}.children[{index}]", issues, depth + 1)

    def validate(self, recommendation: RuleConfigRecommendation) -> RuleConfigRecommendation:
        issues: list[ValidationIssue] = []
        if recommendation.recommendation_type == "insufficient_data":
            recommendation.validation = RecommendationValidation(status="needs_confirmation", issues=[])
            return recommendation

        if self.knowledge.task.id is None:
            issues.append(ValidationIssue(code="task_not_resolved", message="尚未确认任务，不能生成可执行规则草案", path="task"))
        elif recommendation.task.id != self.knowledge.task.id:
            issues.append(ValidationIssue(code="task_mismatch", message="推荐引用的任务与已检索任务不一致", path="task.id"))

        rule = recommendation.proposed_rule
        if not rule.name:
            issues.append(ValidationIssue(code="missing_rule_name", message="规则草案缺少名称", path="proposed_rule.name"))
        if not rule.signals:
            issues.append(ValidationIssue(code="missing_signals", message="规则草案至少需要一个输入信号", path="proposed_rule.signals"))
        for index, signal in enumerate(rule.signals):
            if self.signal_names and signal.name not in self.signal_names:
                issues.append(ValidationIssue(code="unknown_signal", message=f"信号 {signal.name} 不属于当前任务已知信号", path=f"proposed_rule.signals[{index}]"))
            elif not self.signal_names:
                issues.append(ValidationIssue(code="signals_not_verified", message=f"无法验证信号 {signal.name}，当前任务没有信号关系数据", path=f"proposed_rule.signals[{index}]", severity="warning"))
        if rule.judge_condition is None:
            issues.append(ValidationIssue(code="missing_judge_condition", message="规则草案缺少判断条件", path="proposed_rule.judge_condition"))
        self._walk_logic(rule.start_condition, "proposed_rule.start_condition", issues)
        self._walk_logic(rule.judge_condition, "proposed_rule.judge_condition", issues)
        self._walk_logic(rule.end_condition, "proposed_rule.end_condition", issues)

        errors = [issue for issue in issues if issue.severity == "error"]
        recommendation.validation = RecommendationValidation(
            status="invalid" if errors else "needs_confirmation",
            issues=issues,
        )
        if not errors and recommendation.validation.status == "needs_confirmation" and not self.knowledge.data_issues:
            recommendation.validation.status = "valid"
        return recommendation
