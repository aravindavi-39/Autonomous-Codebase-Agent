"""Duplicate code smell detection using conservative AST statement hashing."""

from __future__ import annotations

import ast
import hashlib
from typing import Any

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


def _stmt_signature(node: ast.stmt) -> str:
    """Extract a conservative structural signature of an AST statement."""
    return type(node).__name__


class DuplicateLogicRule(BaseRule):
    """Detects duplicate blocks of logic using structural AST sequence comparison."""

    rule_id = "SMELL-010"
    category = FindingCategory.CODE_SMELL
    title = "Potential duplicate logic"
    default_severity = Severity.LOW
    default_confidence = Confidence.LOW
    description = "Substantial block of identical structural logic found across functions."
    rationale = "Duplicated logic leads to bug fix omissions when only one copy is updated."
    recommendation = "Extract the common statement block into a reusable shared function or utility."

    def __init__(self, min_statements: int = 6) -> None:
        self.min_statements = min_statements

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        blocks: dict[str, list[tuple[str, str, int, int]]] = {}

        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    stmts = node.body
                    if len(stmts) >= self.min_statements:
                        for i in range(len(stmts) - self.min_statements + 1):
                            window = stmts[i : i + self.min_statements]
                            sig = "-".join(_stmt_signature(s) for s in window)
                            h = hashlib.md5(sig.encode("utf-8")).hexdigest()

                            s_line = window[0].lineno
                            e_line = getattr(window[-1], "end_lineno", window[-1].lineno)

                            blocks.setdefault(h, []).append((fa.file_path, node.name, s_line, e_line))

        # Identify duplicate hashes appearing in different functions
        reported_pairs = set()
        for h, occurrences in blocks.items():
            if len(occurrences) > 1:
                # Group by distinct function/file
                unique_funcs = list({(occ[0], occ[1]): occ for occ in occurrences}.values())
                if len(unique_funcs) > 1:
                    primary = unique_funcs[0]
                    dup = unique_funcs[1]
                    pair_key = tuple(sorted([(primary[0], primary[1]), (dup[0], dup[1])]))
                    if pair_key not in reported_pairs:
                        reported_pairs.add(pair_key)
                        evidence = f"Similar {self.min_statements}-statement block also in {dup[0]}:{dup[2]}-{dup[3]} ({dup[1]})"
                        findings.append(
                            self.create_finding(
                                file=primary[0],
                                start_line=primary[2],
                                end_line=primary[3],
                                entity=primary[1],
                                evidence=evidence,
                                description=f"Potential duplicate logic between '{primary[1]}' ({primary[0]}) and '{dup[1]}' ({dup[0]}).",
                            )
                        )

        return findings[:10]  # Cap to prevent noise
