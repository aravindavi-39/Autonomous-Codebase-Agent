"""Import pattern rules: wildcard imports and unused imports."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class WildcardImportRule(BaseRule):
    """Detects wildcard imports (from ... import *)."""

    rule_id = "PAT-002"
    category = FindingCategory.PATTERN
    title = "Wildcard import (from ... import *)"
    default_severity = Severity.LOW
    default_confidence = Confidence.HIGH
    description = "Wildcard import clutters namespace and obfuscates symbol definitions."
    rationale = "Wildcard imports hide where symbols originate, make static analysis difficult, and can lead to name collisions."
    recommendation = "Import only the required symbols explicitly (e.g. 'from module import name')."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            lines = context.get_lines(fa.file_path)
                            s_line = node.lineno
                            e_line = getattr(node, "end_lineno", s_line)
                            mod_name = node.module or ""
                            evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"from {mod_name} import *"

                            findings.append(
                                self.create_finding(
                                    file=fa.file_path,
                                    start_line=s_line,
                                    end_line=e_line,
                                    entity=f"from {mod_name} import *",
                                    evidence=evidence,
                                    description=f"Wildcard import 'from {mod_name} import *' used at {fa.file_path}:{s_line}.",
                                )
                            )
        return findings


class UnusedImportRule(BaseRule):
    """Detects imported modules or symbols that are never referenced in the file."""

    rule_id = "PAT-005"
    category = FindingCategory.PATTERN
    title = "Unused import"
    default_severity = Severity.INFO
    default_confidence = Confidence.MEDIUM
    description = "Imported symbol or module is never referenced in file."
    rationale = "Unused imports clutter source code, introduce unnecessary module coupling, and slow down module loading."
    recommendation = "Remove the unused import statement."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            # Skip __init__.py files where imports are commonly re-exported
            norm_path = fa.file_path.replace("\\", "/")
            if norm_path.endswith("__init__.py"):
                continue

            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            # 1. Collect all referenced identifiers across AST (excluding import statements)
            used_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

            # Check if __all__ is defined
            has_all = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            has_all = True
                            if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        used_names.add(elt.value)

            # 2. Check each import against used_names
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        check_name = alias.asname or alias.name.split(".")[0]
                        if check_name not in used_names:
                            lines = context.get_lines(fa.file_path)
                            s_line = node.lineno
                            e_line = getattr(node, "end_lineno", s_line)
                            evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"import {alias.name}"

                            findings.append(
                                self.create_finding(
                                    file=fa.file_path,
                                    start_line=s_line,
                                    end_line=e_line,
                                    entity=check_name,
                                    evidence=evidence,
                                    description=f"Imported module '{check_name}' appears unused in {fa.file_path}.",
                                )
                            )
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        check_name = alias.asname or alias.name
                        if check_name not in used_names:
                            lines = context.get_lines(fa.file_path)
                            s_line = node.lineno
                            e_line = getattr(node, "end_lineno", s_line)
                            evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"from {node.module} import {alias.name}"

                            findings.append(
                                self.create_finding(
                                    file=fa.file_path,
                                    start_line=s_line,
                                    end_line=e_line,
                                    entity=check_name,
                                    evidence=evidence,
                                    description=f"Imported symbol '{check_name}' appears unused in {fa.file_path}.",
                                )
                            )
        return findings
