"""Tests for CLI verify command: repository verification, JSON mode, flags, and error handling."""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from cli.main import app
from sandbox.copier import compute_directory_fingerprint

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sandbox_test_repo"
runner = CliRunner()


class TestCliVerify:
    def test_verify_command_runs_cleanly(self):
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        result = runner.invoke(app, ["verify", str(FIXTURE_DIR), "--policy", "lenient"])
        assert result.exit_code == 0
        assert "Verification Report" in result.output
        assert "Unit Tests" in result.output
        assert "Lint & Syntax" in result.output
        assert "UNCHANGED" in result.output

        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after

    def test_verify_command_json_mode(self):
        result = runner.invoke(app, ["verify", str(FIXTURE_DIR), "--policy", "lenient", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "verdict" in data
        assert "policy" in data
        assert "test_run" in data
        assert "lint_run" in data
        assert data["source_intact"] is True

    def test_verify_command_no_tests_no_lint(self):
        result = runner.invoke(
            app,
            ["verify", str(FIXTURE_DIR), "--no-tests", "--no-lint", "--policy", "lenient"],
        )
        assert result.exit_code == 0
        assert "SKIPPED" in result.output

    def test_verify_command_export_json(self, tmp_path):
        out_file = tmp_path / "verification_report.json"
        result = runner.invoke(
            app,
            ["verify", str(FIXTURE_DIR), "--policy", "lenient", "--output", str(out_file)],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data["verdict"] in ("PASSED", "WARNING")

    def test_verify_command_nonexistent_repo_fails(self, tmp_path):
        result = runner.invoke(app, ["verify", str(tmp_path / "nonexistent_dir")])
        assert result.exit_code == 1
        assert "does not exist" in result.output.lower()
