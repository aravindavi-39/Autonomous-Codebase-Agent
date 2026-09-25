"""Outdated and problematic coding pattern rules."""

from analysis.findings.pattern_rules.exception_rules import BroadExceptRule
from analysis.findings.pattern_rules.import_rules import UnusedImportRule, WildcardImportRule
from analysis.findings.pattern_rules.syntax_rules import (
    MutableDefaultRule,
    ShadowingBuiltinRule,
    UnreachableCodeRule,
)

__all__ = [
    "BroadExceptRule",
    "MutableDefaultRule",
    "ShadowingBuiltinRule",
    "UnreachableCodeRule",
    "UnusedImportRule",
    "WildcardImportRule",
]
