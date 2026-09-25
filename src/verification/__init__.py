"""Verification engine — test and lint runners, finding delta audits, and policy enforcement.

This package provides:
- Multi-tool code health verification (unit tests, AST syntax and style linting)
- Evidence-based findings delta analysis (confirming target finding elimination)
- Genuinely new finding detection (ensuring zero refactoring regressions)
- Deterministic policy evaluation (STRICT vs. LENIENT modes)
- Read-only target repository verification with SHA-256 immutability validation
"""

from verification.delta_engine import FindingDeltaEngine, findings_match
from verification.engine import VerificationEngine
from verification.linter import AstLinter, LintRunner
from verification.models import (
    FindingDelta,
    LintRunResult,
    LintSeverity,
    LintViolation,
    PolicyMode,
    VerificationPolicy,
    VerificationReport,
    VerificationVerdict,
)
from verification.policy import PolicyEvaluator
from verification.reporter import format_verification_table

__all__ = [
    "AstLinter",
    "FindingDelta",
    "FindingDeltaEngine",
    "LintRunResult",
    "LintRunner",
    "LintSeverity",
    "LintViolation",
    "PolicyEvaluator",
    "PolicyMode",
    "VerificationEngine",
    "VerificationPolicy",
    "VerificationReport",
    "VerificationVerdict",
    "findings_match",
    "format_verification_table",
]
