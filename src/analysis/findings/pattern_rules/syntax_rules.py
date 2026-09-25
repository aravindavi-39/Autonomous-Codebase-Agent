"""Syntax pattern rules: mutable default arguments, shadowing built-ins, unreachable code."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity

SHADOWED_BUILTINS = {
    "id", "type", "list", "dict", "str", "int", "float", "bool", "set",
    "tuple", "bytes", "format", "input", "filter", "map", "all", "any",
    "sum", "min", "max", "open", "dir", "len", "hash", "range",
}


class MutableDefaultRule(BaseRule):
    """Detects mutable default arguments in function definitions."""

    rule_id = "PAT-003"
    category = FindingCategory.PATTERN
    title = "Mutable default argument"
    default_severity = Severity.MEDIUM
    default_confidence = Confidence.HIGH
    description = "Function defines a mutable default value (list, dict, set) in its signature."
    rationale = "Default argument values are evaluated once at module load time. Mutating the default within the function leaks state across subsequent calls."
    recommendation = "Use None as the default value and initialize the mutable object inside the function body (e.g. 'if arg is None: arg = []')."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check positional defaults
                    for default in node.args.defaults + node.args.kw_defaults:
                        if default is None:
                            continue
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            lines = context.get_lines(fa.file_path)
                            s_line = default.lineno
                            e_line = getattr(default, "end_lineno", s_line)
                            evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "def func(arg=[]):"

                            findings.append(
                                self.create_finding(
                                    file=fa.file_path,
                                    start_line=s_line,
                                    end_line=e_line,
                                    entity=node.name,
                                    evidence=evidence,
                                    description=f"Function '{node.name}' has a mutable default argument at line {s_line}.",
                                )
                            )
        return findings


class ShadowingBuiltinRule(BaseRule):
    """Detects function parameters shadowing standard Python built-ins."""

    rule_id = "PAT-004"
    category = FindingCategory.PATTERN
    title = "Shadowing built-in identifier"
    default_severity = Severity.INFO
    default_confidence = Confidence.MEDIUM
    description = "Function parameter shadows a Python built-in function or type name."
    rationale = "Shadowing built-in names like 'id', 'type', or 'list' overrides the built-in symbol in the local scope and can cause obscure bugs."
    recommendation = "Rename the parameter to something more descriptive (e.g. 'item_id', 'type_name', or 'obj_type')."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                        if arg.arg in SHADOWED_BUILTINS:
                            lines = context.get_lines(fa.file_path)
                            s_line = arg.lineno
                            e_line = getattr(arg, "end_lineno", s_line)
                            evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"{arg.arg}"

                            findings.append(
                                self.create_finding(
                                    file=fa.file_path,
                                    start_line=s_line,
                                    end_line=e_line,
                                    entity=arg.arg,
                                    evidence=evidence,
                                    description=f"Parameter '{arg.arg}' in function '{node.name}' shadows Python built-in '{arg.arg}'.",
                                )
                            )
        return findings


class UnreachableCodeRule(BaseRule):
    """Detects unreachable statements following return, raise, break, or continue."""

    rule_id = "PAT-006"
    category = FindingCategory.PATTERN
    title = "Unreachable code"
    default_severity = Severity.LOW
    default_confidence = Confidence.HIGH
    description = "Unreachable code statements detected after a terminal statement in the same block."
    rationale = "Code following a return, raise, break, or continue in the same basic block will never execute, signaling leftover debug code or logic errors."
    recommendation = "Remove unreachable statements or reorganize control flow."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                # Check blocks in functions, if, for, while, try
                for attr in ("body", "orelse", "finalbody"):
                    block = getattr(node, attr, None)
                    if isinstance(block, list) and len(block) > 1:
                        terminated = False
                        for idx, stmt in enumerate(block):
                            if terminated:
                                lines = context.get_lines(fa.file_path)
                                s_line = stmt.lineno
                                e_line = getattr(stmt, "end_lineno", s_line)
                                evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "unreachable statement"

                                findings.append(
                                    self.create_finding(
                                        file=fa.file_path,
                                        start_line=s_line,
                                        end_line=e_line,
                                        evidence=evidence,
                                        description=f"Unreachable code statement '{type(stmt).__name__}' at {fa.file_path}:{s_line}.",
                                    )
                                )
                                break  # Report once per block

                            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                                terminated = True
        return findings
