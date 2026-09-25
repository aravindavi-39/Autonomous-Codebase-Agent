"""Function and method code smell rules: length, parameters, nesting, branches, docstrings."""

from __future__ import annotations

import ast
from typing import Optional

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity
from analysis.models import FunctionInfo


class LongFunctionRule(BaseRule):
    """Detects functions exceeding a length threshold."""

    rule_id = "SMELL-001"
    category = FindingCategory.CODE_SMELL
    title = "Long function"
    default_severity = Severity.LOW
    default_confidence = Confidence.HIGH
    description = "Function exceeds recommended line count."
    rationale = "Long functions are difficult to read, understand, test, and maintain."
    recommendation = "Decompose the function into smaller, focused helper functions with single responsibilities."

    def __init__(self, max_lines: int = 50) -> None:
        self.max_lines = max_lines

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            # Check top-level functions and class methods
            all_funcs: list[FunctionInfo] = list(fa.functions)
            for c in fa.classes:
                all_funcs.extend(c.methods)

            for fn in all_funcs:
                if not fn.end_line or not fn.start_line:
                    continue
                length = fn.end_line - fn.start_line + 1
                if length > self.max_lines:
                    sev = Severity.MEDIUM if length > 100 else Severity.LOW
                    lines = context.get_lines(fa.file_path)
                    evidence = "\n".join(lines[fn.start_line - 1 : min(fn.start_line + 4, fn.end_line)])
                    findings.append(
                        self.create_finding(
                            file=fa.file_path,
                            start_line=fn.start_line,
                            end_line=fn.end_line,
                            entity=fn.name,
                            evidence=evidence,
                            description=f"Function '{fn.name}' is {length} lines long (threshold is {self.max_lines}).",
                            severity=sev,
                        )
                    )
        return findings


class HighParameterCountRule(BaseRule):
    """Detects functions with excessive parameter counts."""

    rule_id = "SMELL-002"
    category = FindingCategory.CODE_SMELL
    title = "High parameter count"
    default_severity = Severity.LOW
    default_confidence = Confidence.HIGH
    description = "Function accepts too many parameters."
    rationale = "Functions with many parameters indicate high coupling and are error-prone to invoke."
    recommendation = "Introduce a parameter object (e.g. dataclass or Pydantic model) to bundle related arguments."

    def __init__(self, max_params: int = 5) -> None:
        self.max_params = max_params

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            all_funcs = list(fa.functions)
            for c in fa.classes:
                all_funcs.extend(c.methods)

            for fn in all_funcs:
                # Exclude self and cls from parameter count
                counted_params = [
                    p.name for p in fn.parameters if p.name not in ("self", "cls")
                ]
                if len(counted_params) > self.max_params:
                    sev = Severity.MEDIUM if len(counted_params) > 7 else Severity.LOW
                    param_list = ", ".join(counted_params)
                    findings.append(
                        self.create_finding(
                            file=fa.file_path,
                            start_line=fn.start_line,
                            end_line=fn.start_line,
                            entity=fn.name,
                            evidence=f"def {fn.name}({param_list}): ...",
                            description=f"Function '{fn.name}' has {len(counted_params)} parameters (threshold is {self.max_params}).",
                            severity=sev,
                        )
                    )
        return findings


class _NestingVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.max_depth = 0
        self.deepest_node: Optional[ast.AST] = None
        self._current_depth = 0

    def _enter_block(self, node: ast.AST) -> None:
        self._current_depth += 1
        if self._current_depth > self.max_depth:
            self.max_depth = self._current_depth
            self.deepest_node = node
        self.generic_visit(node)
        self._current_depth -= 1

    def visit_If(self, node: ast.If) -> None:
        self._enter_block(node)

    def visit_For(self, node: ast.For) -> None:
        self._enter_block(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._enter_block(node)

    def visit_While(self, node: ast.While) -> None:
        self._enter_block(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._enter_block(node)

    def visit_With(self, node: ast.With) -> None:
        self._enter_block(node)


class DeepNestingRule(BaseRule):
    """Detects functions with deeply nested control flow blocks."""

    rule_id = "SMELL-003"
    category = FindingCategory.CODE_SMELL
    title = "Deep nesting"
    default_severity = Severity.MEDIUM
    default_confidence = Confidence.HIGH
    description = "Function contains excessively deep control flow nesting."
    rationale = "Deeply nested code increases cognitive complexity and increases risk of edge-case bugs."
    recommendation = "Use guard clauses (early returns) or extract nested blocks into standalone helper functions."

    def __init__(self, max_depth: int = 4) -> None:
        self.max_depth = max_depth

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    visitor = _NestingVisitor()
                    for item in node.body:
                        visitor.visit(item)

                    if visitor.max_depth >= self.max_depth and visitor.deepest_node:
                        deep_line = getattr(visitor.deepest_node, "lineno", node.lineno)
                        lines = context.get_lines(fa.file_path)
                        evidence = lines[deep_line - 1].strip() if 0 < deep_line <= len(lines) else None
                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=node.lineno,
                                end_line=deep_line,
                                entity=node.name,
                                evidence=evidence,
                                description=f"Function '{node.name}' has nesting depth of {visitor.max_depth} (threshold is {self.max_depth}).",
                            )
                        )
        return findings


class _BranchCounter(ast.NodeVisitor):
    def __init__(self) -> None:
        self.branches = 0

    def visit_If(self, node: ast.If) -> None:
        self.branches += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.branches += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.branches += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.branches += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.branches += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each boolean operand (and, or) adds a branch decision
        self.branches += max(0, len(node.values) - 1)
        self.generic_visit(node)


class TooManyBranchesRule(BaseRule):
    """Detects functions with excessive decision branch points."""

    rule_id = "SMELL-004"
    category = FindingCategory.CODE_SMELL
    title = "Too many branches"
    default_severity = Severity.MEDIUM
    default_confidence = Confidence.MEDIUM
    description = "Function has high cyclomatic branch complexity."
    rationale = "High branch counts require an exponential number of test cases to achieve full path coverage."
    recommendation = "Simplify conditional statements, replace if-chains with lookup tables or polymorphism."

    def __init__(self, max_branches: int = 10) -> None:
        self.max_branches = max_branches

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    counter = _BranchCounter()
                    for item in node.body:
                        counter.visit(item)

                    if counter.branches > self.max_branches:
                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=node.lineno,
                                end_line=getattr(node, "end_lineno", node.lineno),
                                entity=node.name,
                                evidence=f"Branch points: {counter.branches}",
                                description=f"Function '{node.name}' has {counter.branches} branch decisions (threshold is {self.max_branches}).",
                            )
                        )
        return findings


class MissingDocstringRule(BaseRule):
    """Detects public functions or classes without docstrings."""

    rule_id = "SMELL-009"
    category = FindingCategory.CODE_SMELL
    title = "Missing documentation"
    default_severity = Severity.INFO
    default_confidence = Confidence.MEDIUM
    description = "Public class or function lacks docstring documentation."
    rationale = "Public interfaces without documentation increase onboarding friction and maintenance errors."
    recommendation = "Add a docstring explaining purpose, parameters, and return value."

    def __init__(self, min_lines: int = 2) -> None:
        self.min_lines = min_lines

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            # Skip test files and private modules
            f_low = fa.file_path.lower()
            if "test" in f_low or f_low.startswith("_"):
                continue

            # Check public classes
            for cls in fa.classes:
                if not cls.name.startswith("_") and not cls.docstring:
                    cls_len = (cls.end_line or cls.start_line) - cls.start_line + 1
                    if cls_len >= self.min_lines:
                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=cls.start_line,
                                end_line=cls.start_line,
                                entity=cls.name,
                                description=f"Public class '{cls.name}' has no docstring.",
                            )
                        )

            # Check public functions
            for fn in fa.functions:
                if not fn.name.startswith("_") and not fn.docstring:
                    fn_len = (fn.end_line or fn.start_line) - fn.start_line + 1
                    if fn_len >= self.min_lines:
                        findings.append(
                            self.create_finding(
                                file=fa.file_path,
                                start_line=fn.start_line,
                                end_line=fn.start_line,
                                entity=fn.name,
                                description=f"Public function '{fn.name}' has no docstring.",
                            )
                        )
        return findings
