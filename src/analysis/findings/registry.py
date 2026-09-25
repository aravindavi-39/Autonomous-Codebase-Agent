"""Rule registry maintaining and configuring analysis rules."""

from __future__ import annotations

from typing import Optional

from analysis.findings.base_rule import BaseRule
from analysis.findings.models import FindingCategory
from analysis.findings.pattern_rules import (
    BroadExceptRule,
    MutableDefaultRule,
    ShadowingBuiltinRule,
    UnreachableCodeRule,
    UnusedImportRule,
    WildcardImportRule,
)
from analysis.findings.security_rules import (
    CommandInjectionRule,
    DangerousExecutionRule,
    DebugSettingsRule,
    HardcodedSecretRule,
    InsecureTlsRule,
    PathTraversalRule,
    SqlInjectionRule,
    UnsafeDeserializationRule,
    UnsafeSubprocessRule,
    WeakCryptoRule,
)
from analysis.findings.smell_rules import (
    CircularDependencyRule,
    DeadFunctionRule,
    DeepNestingRule,
    DuplicateLogicRule,
    ExcessiveDependenciesRule,
    HighParameterCountRule,
    LargeClassRule,
    LongFunctionRule,
    MissingDocstringRule,
    TooManyBranchesRule,
)


class RuleRegistry:
    """Registry managing available code smell, security, and pattern rules."""

    def __init__(self) -> None:
        self._rules: dict[str, BaseRule] = {}

    def register(self, rule: BaseRule) -> None:
        """Register a new analysis rule."""
        self._rules[rule.rule_id] = rule

    def unregister(self, rule_id: str) -> None:
        """Unregister a rule by ID."""
        self._rules.pop(rule_id, None)

    def get_rule(self, rule_id: str) -> Optional[BaseRule]:
        """Retrieve a specific rule by ID."""
        return self._rules.get(rule_id)

    def get_rules(
        self,
        enable_security: bool = True,
        enable_smells: bool = True,
        enable_patterns: bool = True,
        category: Optional[FindingCategory] = None,
    ) -> list[BaseRule]:
        """Return active rules filtered by category toggles."""
        selected: list[BaseRule] = []
        for rule in self._rules.values():
            if rule.category == FindingCategory.SECURITY and not enable_security:
                continue
            if rule.category == FindingCategory.CODE_SMELL and not enable_smells:
                continue
            if rule.category == FindingCategory.PATTERN and not enable_patterns:
                continue
            if category is not None and rule.category != category:
                continue
            selected.append(rule)
        return selected


def get_default_registry() -> RuleRegistry:
    """Instantiate and populate the default RuleRegistry with all built-in rules."""
    registry = RuleRegistry()

    # 1. Code Smells
    registry.register(LongFunctionRule())
    registry.register(HighParameterCountRule())
    registry.register(DeepNestingRule())
    registry.register(TooManyBranchesRule())
    registry.register(LargeClassRule())
    registry.register(DeadFunctionRule())
    registry.register(CircularDependencyRule())
    registry.register(ExcessiveDependenciesRule())
    registry.register(MissingDocstringRule())
    registry.register(DuplicateLogicRule())

    # 2. Security Vulnerabilities
    registry.register(HardcodedSecretRule())
    registry.register(DangerousExecutionRule())
    registry.register(UnsafeSubprocessRule())
    registry.register(UnsafeDeserializationRule())
    registry.register(SqlInjectionRule())
    registry.register(CommandInjectionRule())
    registry.register(PathTraversalRule())
    registry.register(WeakCryptoRule())
    registry.register(InsecureTlsRule())
    registry.register(DebugSettingsRule())

    # 3. Coding Patterns
    registry.register(BroadExceptRule())
    registry.register(WildcardImportRule())
    registry.register(MutableDefaultRule())
    registry.register(ShadowingBuiltinRule())
    registry.register(UnusedImportRule())
    registry.register(UnreachableCodeRule())

    return registry
