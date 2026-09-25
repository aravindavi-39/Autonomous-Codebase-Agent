"""Configuration security rules: TLS verification disabled, insecure debug settings."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class InsecureTlsRule(BaseRule):
    """Detects disabled TLS/SSL certificate verification."""

    rule_id = "SEC-009"
    category = FindingCategory.SECURITY
    title = "Disabled TLS/SSL certificate verification"
    default_severity = Severity.HIGH
    default_confidence = Confidence.HIGH
    description = "TLS/SSL certificate validation is explicitly disabled (verify=False)."
    rationale = "Disabling certificate validation allows attackers in the network path to eavesdrop or tamper with communication (MITM attack)."
    recommendation = "Enable certificate verification (verify=True) and ensure appropriate root certificates are installed."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check verify=False keyword argument
                    for kw in node.keywords:
                        if kw.arg == "verify":
                            if (isinstance(kw.value, ast.Constant) and kw.value.value is False) or (
                                isinstance(kw.value, ast.Name) and kw.value.id == "False"
                            ):
                                lines = context.get_lines(fa.file_path)
                                s_line = node.lineno
                                e_line = getattr(node, "end_lineno", s_line)
                                evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "verify=False"

                                findings.append(
                                    self.create_finding(
                                        file=fa.file_path,
                                        start_line=s_line,
                                        end_line=e_line,
                                        evidence=evidence,
                                        description=f"Insecure network communication: certificate verification disabled with 'verify=False' at {fa.file_path}:{s_line}.",
                                    )
                                )

                    # Check ssl._create_unverified_context
                    if isinstance(node.func, ast.Attribute) and node.func.attr == "_create_unverified_context":
                        lines = context.get_lines(fa.file_path)
                        s_line = node.lineno
                        e_line = getattr(node, "end_lineno", s_line)
                        evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "_create_unverified_context()"
                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=s_line,
                                end_line=e_line,
                                entity="_create_unverified_context",
                                evidence=evidence,
                                description=f"Unverified SSL context created via '_create_unverified_context()' at {fa.file_path}:{s_line}.",
                            )
                        )
        return findings


class DebugSettingsRule(BaseRule):
    """Detects enabled debug mode or insecure development configuration."""

    rule_id = "SEC-010"
    category = FindingCategory.SECURITY
    title = "Insecure debug mode enabled"
    default_severity = Severity.LOW
    default_confidence = Confidence.MEDIUM
    description = "Application or web framework is configured with debug mode explicitly enabled."
    rationale = "Enabling debug mode in production can expose interactive execution consoles, sensitive environment variables, and stack traces."
    recommendation = "Ensure debug mode is disabled in production environments and controlled via environment variables (e.g. DEBUG=False)."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                # 1. app.run(debug=True)
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == "debug":
                            if (isinstance(kw.value, ast.Constant) and kw.value.value is True) or (
                                isinstance(kw.value, ast.Name) and kw.value.id == "True"
                            ):
                                lines = context.get_lines(fa.file_path)
                                s_line = node.lineno
                                e_line = getattr(node, "end_lineno", s_line)
                                evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "debug=True"

                                findings.append(
                                    self.create_finding(
                                        file=fa.file_path,
                                        start_line=s_line,
                                        end_line=e_line,
                                        evidence=evidence,
                                        description=f"Debug mode explicitly enabled via 'debug=True' at {fa.file_path}:{s_line}.",
                                    )
                                )

                # 2. Top-level assignment DEBUG = True
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "DEBUG":
                            if (isinstance(node.value, ast.Constant) and node.value.value is True) or (
                                isinstance(node.value, ast.Name) and node.value.id == "True"
                            ):
                                lines = context.get_lines(fa.file_path)
                                s_line = node.lineno
                                e_line = getattr(node, "end_lineno", s_line)
                                evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "DEBUG = True"

                                findings.append(
                                    self.create_finding(
                                        file=fa.file_path,
                                        start_line=s_line,
                                        end_line=e_line,
                                        evidence=evidence,
                                        description=f"Constant 'DEBUG' is hardcoded to True at {fa.file_path}:{s_line}.",
                                    )
                                )
        return findings
