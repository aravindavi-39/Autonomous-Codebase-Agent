"""Class-level code smell rules: large classes / God classes."""

from __future__ import annotations

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class LargeClassRule(BaseRule):
    """Detects classes with excessive lines or too many methods."""

    rule_id = "SMELL-005"
    category = FindingCategory.CODE_SMELL
    title = "Large class"
    default_severity = Severity.MEDIUM
    default_confidence = Confidence.HIGH
    description = "Class exceeds method count or line threshold, indicating too many responsibilities."
    rationale = "Large classes ('God Classes') centralize excessive system responsibility and are hard to refactor safely."
    recommendation = "Decompose the class into smaller, specialized classes adhering to the Single Responsibility Principle."

    def __init__(self, max_lines: int = 200, max_methods: int = 15) -> None:
        self.max_lines = max_lines
        self.max_methods = max_methods

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            for cls in fa.classes:
                if not cls.end_line or not cls.start_line:
                    continue

                line_count = cls.end_line - cls.start_line + 1
                method_count = len(cls.methods)

                reasons: list[str] = []
                if line_count > self.max_lines:
                    reasons.append(f"{line_count} lines (threshold: {self.max_lines})")
                if method_count > self.max_methods:
                    reasons.append(f"{method_count} methods (threshold: {self.max_methods})")

                if reasons:
                    evidence_str = f"Class {cls.name} with {method_count} methods across {line_count} lines"
                    findings.append(
                        self.create_finding(
                            file=fa.file_path,
                            start_line=cls.start_line,
                            end_line=cls.end_line,
                            entity=cls.name,
                            evidence=evidence_str,
                            description=f"Class '{cls.name}' is too large: {', '.join(reasons)}.",
                        )
                    )
        return findings
