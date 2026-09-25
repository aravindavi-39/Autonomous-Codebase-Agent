"""Injection vulnerability rules: subprocess shell=True, SQL injection, command injection, path traversal."""

from __future__ import annotations

import ast

from analysis.findings.base_rule import BaseRule
from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


def _is_dynamic_string(node: ast.AST) -> bool:
    """Return True if AST node represents dynamic string construction."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
        return True
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            return True
    return False


class UnsafeSubprocessRule(BaseRule):
    """Detects subprocess invocations with shell=True."""

    rule_id = "SEC-003"
    category = FindingCategory.SECURITY
    title = "Unsafe subprocess execution (shell=True)"
    default_severity = Severity.HIGH
    default_confidence = Confidence.HIGH
    description = "Subprocess invoked with shell=True."
    rationale = "Invoking a subshell enables shell command injection when arguments contain unescaped shell metacharacters."
    recommendation = "Avoid shell=True and pass arguments as a list of strings after validating inputs."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check if call is subprocess.<something> or Popen/run/call
                    is_subproc = False
                    if isinstance(node.func, ast.Attribute):
                        attr = node.func.attr
                        if attr in ("run", "Popen", "call", "check_call", "check_output"):
                            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                                is_subproc = True
                            elif attr in ("run", "Popen", "call"):
                                is_subproc = True

                    if is_subproc:
                        for kw in node.keywords:
                            if kw.arg == "shell":
                                # Check if True
                                if (isinstance(kw.value, ast.Constant) and kw.value.value is True) or (
                                    isinstance(kw.value, ast.Name) and kw.value.id == "True"
                                ):
                                    lines = context.get_lines(fa.file_path)
                                    s_line = node.lineno
                                    e_line = getattr(node, "end_lineno", s_line)
                                    evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "subprocess.run(..., shell=True)"

                                    findings.append(
                                        self.create_finding(
                                            file=fa.file_path,
                                            start_line=s_line,
                                            end_line=e_line,
                                            entity="subprocess",
                                            evidence=evidence,
                                            description=f"Potential command injection risk detected via subprocess with shell=True at {fa.file_path}:{s_line}.",
                                        )
                                    )
        return findings


class SqlInjectionRule(BaseRule):
    """Detects SQL execution with string-formatted dynamic queries."""

    rule_id = "SEC-005"
    category = FindingCategory.SECURITY
    title = "Potential SQL injection risk"
    default_severity = Severity.HIGH
    default_confidence = Confidence.MEDIUM
    description = "SQL execution method invoked with dynamically formatted query string."
    rationale = "Formatting strings directly into SQL queries allows untrusted input to alter query syntax and access unauthorized data."
    recommendation = "Use parameterized queries with placeholder bindings instead of string interpolation."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            # Map variables assigned dynamic strings
            dynamic_vars: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and _is_dynamic_string(node.value):
                            dynamic_vars.add(target.id)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany"):
                        if node.args:
                            first_arg = node.args[0]
                            is_vuln = _is_dynamic_string(first_arg)
                            if not is_vuln and isinstance(first_arg, ast.Name) and first_arg.id in dynamic_vars:
                                is_vuln = True

                            if is_vuln:
                                lines = context.get_lines(fa.file_path)
                                s_line = node.lineno
                                e_line = getattr(node, "end_lineno", s_line)
                                evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "cursor.execute(...)"

                                findings.append(
                                    self.create_finding(
                                        file=fa.file_path,
                                        start_line=s_line,
                                        end_line=e_line,
                                        entity=node.func.attr,
                                        evidence=evidence,
                                        description=f"Potential SQL injection risk: dynamic string passed to '{node.func.attr}()' at {fa.file_path}:{s_line}.",
                                    )
                                )
        return findings


class CommandInjectionRule(BaseRule):
    """Detects command execution via os.system or os.popen with dynamic strings."""

    rule_id = "SEC-006"
    category = FindingCategory.SECURITY
    title = "Potential command injection risk"
    default_severity = Severity.HIGH
    default_confidence = Confidence.MEDIUM
    description = "Use of os.system() or os.popen() with dynamically formatted command string."
    rationale = "Passing dynamic command strings to system shells allows attackers to append arbitrary commands."
    recommendation = "Use subprocess.run with argument lists and shell=False instead of os.system()."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr in ("system", "popen"):
                        is_os = False
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                            is_os = True
                        elif node.func.attr in ("system", "popen"):
                            is_os = True

                        if is_os and node.args:
                            arg0 = node.args[0]
                            # If argument is dynamic or variable
                            if _is_dynamic_string(arg0) or isinstance(arg0, ast.Name):
                                lines = context.get_lines(fa.file_path)
                                s_line = node.lineno
                                e_line = getattr(node, "end_lineno", s_line)
                                evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else f"os.{node.func.attr}(...)"

                                findings.append(
                                    self.create_finding(
                                        file=fa.file_path,
                                        start_line=s_line,
                                        end_line=e_line,
                                        entity=f"os.{node.func.attr}",
                                        evidence=evidence,
                                        description=f"Potential command injection risk detected because dynamic argument is executed via 'os.{node.func.attr}()'.",
                                    )
                                )
        return findings


class PathTraversalRule(BaseRule):
    """Detects unsafe file open operations with dynamic unvalidated paths."""

    rule_id = "SEC-007"
    category = FindingCategory.SECURITY
    title = "Potential path traversal risk"
    default_severity = Severity.MEDIUM
    default_confidence = Confidence.LOW
    description = "File open operation uses dynamic path construction without visible boundary validation."
    rationale = "Unsanitized path arguments may contain directory traversal sequences ('../') allowing access outside intended directories."
    recommendation = "Validate that resolved paths are strictly contained within the intended base directory using is_path_within() or os.path.basename()."

    def check(self, context: AnalysisContext) -> list[Finding]:
        findings: list[Finding] = []
        for fa in context.code_index.file_analyses:
            # Skip test files and internal readers
            if "test" in fa.file_path.lower() or "ingestion" in fa.file_path.lower():
                continue

            tree = context.get_ast(fa.file_path)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_id = None
                    if isinstance(node.func, ast.Name) and node.func.id == "open":
                        func_id = "open"
                    elif isinstance(node.func, ast.Attribute) and node.func.attr == "open":
                        func_id = "open"

                    if func_id and node.args:
                        path_arg = node.args[0]
                        if _is_dynamic_string(path_arg):
                            lines = context.get_lines(fa.file_path)
                            s_line = node.lineno
                            e_line = getattr(node, "end_lineno", s_line)
                            evidence = lines[s_line - 1].strip() if 0 < s_line <= len(lines) else "open(...)"

                            findings.append(
                                self.create_finding(
                                    file=fa.file_path,
                                    start_line=s_line,
                                    end_line=e_line,
                                    entity="open",
                                    evidence=evidence,
                                    description=f"Potential path traversal risk detected because path is constructed dynamically in 'open()' at {fa.file_path}:{s_line}.",
                                )
                            )
        return findings
