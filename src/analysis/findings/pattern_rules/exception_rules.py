"""Exception handling pattern rules: broad except clauses."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class BroadExceptRule(BaseRule):
    """Detects overly broad except clauses (bare except or except Exception) that suppress errors."""

    rule_id = "PAT-001"
    category = FindingCategory.PATTERN
    title = "Broad exception clause"
    default_severity = Severity.LOW
    default_confidence = Confidence.HIGH
    description = "Broad except clause catches all exceptions and silently suppresses or masks errors."
    rationale = "Catching bare Exception hides unexpected bugs, KeyboardInterrupt, memory errors, and syntax defects."
    recommendation = "Catch specific expected exception types (e.g. ValueError, FileNotFoundError) and log or handle the error."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    is_broad = False
                    reason = ""
                    if node.type is None:
                        is_broad = True
                        reason = "bare 'except:'"
                    elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                        is_broad = True
                        reason = f"'except {node.type.id}:'"

                    if is_broad:
                        lines = context.get_lines(fa.file_path)
                        s_line = node.lineno
                        e_line = getattr(node, "end_lineno", s_line)
                        evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else reason

                        # Check if body contains only pass or ...
                        swallowed = len(node.body) == 1 and isinstance(
                            node.body[0], (ast.Pass, ast.Expr)
                        )
                        sev = Severity.MEDIUM if swallowed else Severity.LOW

                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=s_line,
                                end_line=e_line,
                                title=f"Broad exception handler ({reason})",
                                evidence=evidence,
                                severity=sev,
                                description=f"Broad exception handler ({reason}) at {fa.file_path}:{s_line}.",
                            )
                        )
        return findings
