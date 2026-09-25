"""Weak cryptography detection rule: MD5, SHA-1."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class WeakCryptoRule(BaseRule):
    """Detects usage of weak or broken hash algorithms (MD5, SHA-1)."""

    rule_id = "SEC-008"
    category = FindingCategory.SECURITY
    title = "Weak cryptographic hash function (MD5/SHA-1)"
    default_severity = Severity.LOW
    default_confidence = Confidence.LOW
    description = "Use of MD5 or SHA-1 hash function detected."
    rationale = "MD5 and SHA-1 have known collision vulnerabilities. If used for security purposes (passwords, signatures) they are broken; if used only for non-cryptographic cache keys or file integrity checks they are benign."
    recommendation = "Use SHA-256 (hashlib.sha256) or SHA-3 for security-sensitive hashing. Verify if this hash is used in a cryptographic context."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    weak_algo = None
                    if isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                            if node.func.attr in ("md5", "sha1"):
                                weak_algo = node.func.attr
                    elif isinstance(node.func, ast.Name):
                        if node.func.id in ("md5", "sha1"):
                            weak_algo = node.func.id

                    if weak_algo:
                        lines = context.get_lines(fa.file_path)
                        s_line = node.lineno
                        e_line = getattr(node, "end_lineno", s_line)
                        evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"hashlib.{weak_algo}(...)"

                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=s_line,
                                end_line=e_line,
                                entity=weak_algo.upper(),
                                evidence=evidence,
                                description=f"Potential weak cryptography: '{weak_algo.upper()}' called at {fa.file_path}:{s_line}. Verify if used in a security context.",
                            )
                        )
        return findings
