"""Refactoring engine — planning, diff generation, and change validation.

This package provides:
- Structured models for refactoring plans, change proposals, and diffs
- Deterministic refactoring strategies mapped to analysis findings
- A planner that produces prioritized refactoring plans
- A diff generator producing unified diffs
- A validator ensuring diffs are safe and consistent
- Rich terminal preview formatting

No changes are ever applied to the original repository. The user must
explicitly approve any future patch application.
"""

from refactoring.models import (
    ChangeProposal,
    DiffResult,
    FileChange,
    RefactoringAction,
    RefactoringPlan,
    SafetyClassification,
    TextEdit,
    ValidationResult,
)
from refactoring.strategies import (
    BaseStrategy,
    StrategyRegistry,
    get_default_strategy_registry,
)
from refactoring.planner import RefactoringPlanner
from refactoring.generator import DiffGenerator
from refactoring.validator import DiffValidator

__all__ = [
    "ChangeProposal",
    "DiffResult",
    "FileChange",
    "RefactoringAction",
    "RefactoringPlan",
    "SafetyClassification",
    "TextEdit",
    "ValidationResult",
    "BaseStrategy",
    "StrategyRegistry",
    "get_default_strategy_registry",
    "RefactoringPlanner",
    "DiffGenerator",
    "DiffValidator",
]
