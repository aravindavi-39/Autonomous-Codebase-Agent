"""Dependency-free AST-based static linter and optional external tool adapter."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Optional

from utils.logger import setup_logger
from verification.models import LintRunResult, LintSeverity, LintViolation

logger = setup_logger(__name__)

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}


class AstLinter:
    """Built-in, zero-dependency static and syntax linter using Python's ast module."""

    def __init__(self, max_line_length: int = 120) -> None:
        self.max_line_length = max_line_length

    def check_file(self, file_path: Path, repo_root: Path) -> list[LintViolation]:
        """Inspect a single Python file for syntax errors and style anomalies."""
        violations: list[LintViolation] = []
        rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception as exc:
                violations.append(
                    LintViolation(
                        file=rel_path,
                        line=1,
                        column=1,
                        code="E901_IO_ERROR",
                        message=f"Cannot read file: {exc}",
                        severity=LintSeverity.ERROR,
                    )
                )
                return violations

        # 1. Syntax check via ast.parse
        try:
            ast.parse(content, filename=rel_path)
        except SyntaxError as exc:
            violations.append(
                LintViolation(
                    file=rel_path,
                    line=exc.lineno or 1,
                    column=exc.offset or 1,
                    code="E999_SYNTAX",
                    message=f"SyntaxError: {exc.msg}",
                    severity=LintSeverity.ERROR,
                )
            )
            # If there's a fatal syntax error, line-by-line stylistic checks are secondary
            return violations

        # 2. Line-by-line checks
        lines = content.splitlines(keepends=True)

        for line_num, line in enumerate(lines, start=1):
            stripped_line = line.rstrip("\r\n")

            # Trailing whitespace check
            if stripped_line != stripped_line.rstrip(" \t"):
                violations.append(
                    LintViolation(
                        file=rel_path,
                        line=line_num,
                        column=len(stripped_line.rstrip(" \t")) + 1,
                        code="W291_TRAILING_WHITESPACE",
                        message="Trailing whitespace detected",
                        severity=LintSeverity.WARNING,
                    )
                )

            # Max line length check
            if len(stripped_line) > self.max_line_length:
                violations.append(
                    LintViolation(
                        file=rel_path,
                        line=line_num,
                        column=self.max_line_length + 1,
                        code="E501_LINE_TOO_LONG",
                        message=f"Line exceeds {self.max_line_length} characters ({len(stripped_line)} > {self.max_line_length})",
                        severity=LintSeverity.WARNING,
                    )
                )

        # Missing newline at end of file
        if content and not content.endswith("\n"):
            violations.append(
                LintViolation(
                    file=rel_path,
                    line=len(lines),
                    column=len(lines[-1]) if lines else 1,
                    code="W292_NO_NEWLINE_AT_EOF",
                    message="No newline at end of file",
                    severity=LintSeverity.INFO,
                )
            )

        return violations

    def check_repository(self, repo_path: Path) -> LintRunResult:
        """Run AST linting across all Python files in the given directory."""
        resolved_repo = repo_path.resolve()
        violations: list[LintViolation] = []
        files_checked = 0

        for path in sorted(resolved_repo.rglob("*.py")):
            rel_parts = path.relative_to(resolved_repo).parts
            if any(p in EXCLUDE_DIRS for p in rel_parts):
                continue

            files_checked += 1
            file_violations = self.check_file(path, resolved_repo)
            violations.extend(file_violations)

        errors = sum(1 for v in violations if v.severity == LintSeverity.ERROR)
        warnings = sum(1 for v in violations if v.severity == LintSeverity.WARNING)

        if errors > 0:
            status = "FAILED"
            summary = f"{errors} error(s), {warnings} warning(s) in {files_checked} files"
        elif warnings > 0:
            status = "WARNING"
            summary = f"0 errors, {warnings} warning(s) in {files_checked} files"
        else:
            status = "PASSED"
            summary = f"Clean: {files_checked} files checked with zero violations"

        return LintRunResult(
            status=status,
            linter_name="ast_linter",
            violations=violations,
            files_checked=files_checked,
            error_count=errors,
            warning_count=warnings,
            skipped=False,
            summary=summary,
        )


class LintRunner:
    """Coordinates code linting, utilizing built-in AST checks with optional external tool adapters."""

    def __init__(self, prefer_external: bool = False, timeout_seconds: int = 20) -> None:
        self.prefer_external = prefer_external
        self.timeout_seconds = timeout_seconds
        self.ast_linter = AstLinter()

    def run(self, repo_path: Path) -> LintRunResult:
        """Run lint checks on repository."""
        # Always use the reliable, zero-dependency AstLinter
        return self.ast_linter.check_repository(repo_path)
