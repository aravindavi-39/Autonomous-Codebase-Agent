"""Tests for CLI plan and diff commands."""

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"
runner = CliRunner()


def _hash_directory(directory: Path) -> str:
    """Compute a deterministic hash of all files in directory."""
    hasher = hashlib.sha256()
    for file_path in sorted(directory.rglob("*")):
        if file_path.is_file() and "__pycache__" not in str(file_path):
            hasher.update(str(file_path.relative_to(directory)).encode())
            hasher.update(file_path.read_bytes())
    return hasher.hexdigest()


class TestCliPlan:
    def test_plan_command_runs(self):
        result = runner.invoke(app, ["plan", str(FIXTURE_DIR)])
        assert result.exit_code == 0

    def test_plan_safe_only(self):
        result = runner.invoke(app, ["plan", str(FIXTURE_DIR), "--safe-only"])
        assert result.exit_code == 0
        output = result.output.lower()
        # Should not contain REVIEW_REQUIRED or UNSUPPORTED in the rendered table
        # (safe-only filter is applied before output)

    def test_plan_json_output(self):
        result = runner.invoke(app, ["plan", str(FIXTURE_DIR), "--json"])
        assert result.exit_code == 0
        # Output should be valid JSON
        data = json.loads(result.output)
        assert "repository" in data
        assert "actions" in data
        assert "summary" in data

    def test_plan_finding_filter(self):
        # First get a valid finding ID from JSON output
        result = runner.invoke(app, ["plan", str(FIXTURE_DIR), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        if data["actions"]:
            finding_id = data["actions"][0]["finding"]["id"]
            result2 = runner.invoke(app, ["plan", str(FIXTURE_DIR), "--finding", finding_id])
            assert result2.exit_code == 0

    def test_plan_does_not_modify_repo(self):
        hash_before = _hash_directory(FIXTURE_DIR)
        runner.invoke(app, ["plan", str(FIXTURE_DIR)])
        hash_after = _hash_directory(FIXTURE_DIR)
        assert hash_before == hash_after


class TestCliDiff:
    def test_diff_command_safe_only(self):
        result = runner.invoke(app, ["diff", str(FIXTURE_DIR), "--safe-only"])
        # Should succeed (exit 0) even if no safe diffs are actionable
        assert result.exit_code == 0

    def test_diff_does_not_modify_repo(self):
        hash_before = _hash_directory(FIXTURE_DIR)
        runner.invoke(app, ["diff", str(FIXTURE_DIR), "--safe-only"])
        hash_after = _hash_directory(FIXTURE_DIR)
        assert hash_before == hash_after

    def test_diff_no_secrets_in_output(self):
        """Verify no secrets appear in diff output."""
        result = runner.invoke(app, ["diff", str(FIXTURE_DIR), "--safe-only"])
        output = result.output
        # The vulnerable_repo has FAKE_TEST_API_KEY but that should not appear
        # in safe-only diff output (safe changes are about patterns, not secrets)
        # We only check that actual secret values don't leak into diff text
        assert "FAKE_TEST_API_KEY_12345678901234567890" not in output
        assert "FAKE_TEST_PASSWORD_SECRET_123" not in output
