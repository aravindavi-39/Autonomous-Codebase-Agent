"""Code smell detection rules."""

from analysis.findings.smell_rules.class_smells import LargeClassRule
from analysis.findings.smell_rules.duplication_smells import DuplicateLogicRule
from analysis.findings.smell_rules.function_smells import (
    DeepNestingRule,
    HighParameterCountRule,
    LongFunctionRule,
    MissingDocstringRule,
    TooManyBranchesRule,
)
from analysis.findings.smell_rules.graph_smells import (
    CircularDependencyRule,
    DeadFunctionRule,
    ExcessiveDependenciesRule,
)

__all__ = [
    "CircularDependencyRule",
    "DeadFunctionRule",
    "DeepNestingRule",
    "DuplicateLogicRule",
    "ExcessiveDependenciesRule",
    "HighParameterCountRule",
    "LargeClassRule",
    "LongFunctionRule",
    "MissingDocstringRule",
    "TooManyBranchesRule",
]
