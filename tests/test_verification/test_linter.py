"""Tests for AstLinter: syntax checking, style violations, and repository lint runs."""

from pathlib import Path
import pytest

from verification.linter import AstLinter, LintRunner
from verification.models import LintSeverity


class TestAstLinter:
    def test_clean_file_passes(self, tmp_path):
        clean_file = tmp_path / "clean.py"
        clean_file.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

        linter = AstLinter()
        violations = linter.check_file(clean_file, tmp_path)
        assert len(violations) == 0

    def test_detects_syntax_error(self, tmp_path):
        broken_file = tmp_path / "broken.py"
        broken_file.write_text("def broken(x:\n    return x\n", encoding="utf-8")

        linter = AstLinter()
        violations = linter.check_file(broken_file, tmp_path)
        assert len(violations) > 0
        syntax_errors = [v for v in violations if v.severity == LintSeverity.ERROR]
        assert len(syntax_errors) == 1
        assert syntax_errors[0].code == "E999_SYNTAX"
        assert "SyntaxError" in syntax_errors[0].message

    def test_detects_trailing_whitespace(self, tmp_path):
        ws_file = tmp_path / "whitespace.py"
        ws_file.write_text("x = 10    \ny = 20\n", encoding="utf-8")

        linter = AstLinter()
        violations = linter.check_file(ws_file, tmp_path)
        ws_violations = [v for v in violations if v.code == "W291_TRAILING_WHITESPACE"]
        assert len(ws_violations) == 1
        assert ws_violations[0].line == 1

    def test_detects_line_too_long(self, tmp_path):
        long_file = tmp_path / "long_line.py"
        long_content = "# " + "a" * 130 + "\n"
        long_file.write_text(long_content, encoding="utf-8")

        linter = AstLinter(max_line_length=120)
        violations = linter.check_file(long_file, tmp_path)
        long_violations = [v for v in violations if v.code == "E501_LINE_TOO_LONG"]
        assert len(long_violations) == 1

    def test_detects_missing_newline_at_eof(self, tmp_path):
        no_nl_file = tmp_path / "no_nl.py"
        no_nl_file.write_text("x = 1", encoding="utf-8")

        linter = AstLinter()
        violations = linter.check_file(no_nl_file, tmp_path)
        eof_violations = [v for v in violations if v.code == "W292_NO_NEWLINE_AT_EOF"]
        assert len(eof_violations) == 1

    def test_check_repository_aggregates(self, tmp_path):
        (tmp_path / "good.py").write_text("def a(): pass\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text("def b(\n", encoding="utf-8")

        runner = LintRunner()
        result = runner.run(tmp_path)
        assert result.status == "FAILED"
        assert result.error_count >= 1
        assert result.files_checked == 2
