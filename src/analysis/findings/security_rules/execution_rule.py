"""Dangerous dynamic execution rule: eval(), exec(), and dynamic compile()."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class DangerousExecutionRule(BaseRule):
    """Detects dangerous dynamic execution functions (eval, exec, compile)."""

    rule_id = "SEC-002"
    category = FindingCategory.SECURITY
    title = "Dangerous dynamic execution (eval/exec)"
    default_severity = Severity.HIGH
    default_confidence = Confidence.HIGH
    description = "Use of eval(), exec(), or dynamic compile() detected."
    rationale = "Dynamic execution of strings allows arbitrary code execution if any part of the string originates from untrusted input."
    recommendation = "Avoid eval() and exec(). Use ast.literal_eval() for safe parsing of literals or use structured data like JSON."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in ("eval", "exec") or (
                        func_name == "compile" and len(node.args) >= 3
                    ):
                        lines = context.get_lines(fa.file_path)
                        s_line = node.lineno
                        e_line = getattr(node, "end_lineno", s_line)
                        evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"{func_name}(...)"

                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=s_line,
                                end_line=e_line,
                                entity=func_name,
                                evidence=evidence,
                                description=f"Potential arbitrary code execution risk via '{func_name}()' at {fa.file_path}:{s_line}.",
                            )
                        )
        return findings
