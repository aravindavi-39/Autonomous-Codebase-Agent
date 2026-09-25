"""Unsafe deserialization rule: pickle.load / pickle.loads."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class UnsafeDeserializationRule(BaseRule):
    """Detects unsafe deserialization via pickle."""

    rule_id = "SEC-004"
    category = FindingCategory.SECURITY
    title = "Unsafe deserialization (pickle)"
    default_severity = Severity.HIGH
    default_confidence = Confidence.HIGH
    description = "Use of pickle.load() or pickle.loads() detected."
    rationale = "Pickle payloads can instantiate arbitrary Python classes and invoke __reduce__ methods to execute malicious commands."
    recommendation = "Use safe data serialization formats like JSON, MessagePack, or Protocol Buffers instead of pickle for untrusted input."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr in ("load", "loads"):
                        is_pickle = False
                        if isinstance(node.func.value, ast.Name) and node.func.value.id in ("pickle", "_pickle", "cPickle"):
                            is_pickle = True

                        if is_pickle:
                            lines = context.get_lines(fa.file_path)
                            s_line = node.lineno
                            e_line = getattr(node, "end_lineno", s_line)
                            evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"pickle.{node.func.attr}(...)"

                            findings.append(
                                self.create_finding(
                                    file=fa.file_path,
                                    start_line=s_line,
                                    end_line=e_line,
                                    entity=f"pickle.{node.func.attr}",
                                    evidence=evidence,
                                    description=f"Potential arbitrary code execution risk via unsafe deserialization with 'pickle.{node.func.attr}()' at {fa.file_path}:{s_line}.",
                                )
                            )
        return findings
