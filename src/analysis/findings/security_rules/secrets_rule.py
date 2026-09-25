"""Hardcoded secrets detection rule."""

from __future__ import annotations

import re

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity
from utils.secrets import contains_secrets, redact_secrets


class HardcodedSecretRule(BaseRule):
    """Detects hardcoded secrets, API keys, tokens, and credentials in source code."""

    rule_id = "SEC-001"
    category = FindingCategory.SECURITY
    title = "Hardcoded secret or credential"
    default_severity = Severity.HIGH
    default_confidence = Confidence.HIGH
    description = "Hardcoded secret, API key, token, or password assignment detected in source code."
    rationale = "Hardcoded credentials can be committed to version control and exposed to unauthorized parties."
    recommendation = "Remove hardcoded credentials and load them from environment variables or a secret vault."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for file_rec in context.manifest.files:
            # Skip binaries
            if file_rec.metadata.is_binary:
                continue

            rel_path = file_rec.relative_path
            lines = context.get_lines(rel_path)

            for idx, line in enumerate(lines, 1):
                # Don't check comments that clearly explain fake test credentials
                if "fake" in line.lower() and "test" in line.lower() and not ("=" in line or ":" in line):
                    continue

                if contains_secrets(line):
                    # Redact the actual secret in the evidence so it never leaks
                    clean_evidence = redact_secrets(line.strip())
                    sev = Severity.CRITICAL if "sk-" in line or "PRIVATE KEY" in line else Severity.HIGH
                    findings.append(
                        self.create_finding(
                            file=rel_path,
                            start_line=idx,
                            end_line=idx,
                            evidence=clean_evidence,
                            severity=sev,
                            description=f"Potential hardcoded secret or credential detected in '{rel_path}:{idx}'.",
                        )
                    )
        return findings
