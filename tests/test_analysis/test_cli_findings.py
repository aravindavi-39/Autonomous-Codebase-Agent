"""Tests for CLI analyze findings extensions."""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


@pytest.fixture
def vulnerable_repo_path():
    return str(Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo")


@pytest.fixture
def sample_repo_path():
    return str(Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo")


def test_cli_analyze_default_shows_findings(vulnerable_repo_path):
    result = runner.invoke(app, ["analyze", vulnerable_repo_path])
    assert result.exit_code == 0
    assert "Codebase Analysis Report" in result.stdout
    assert "Security Findings" in result.stdout or "Code Smells" in result.stdout
    assert "CRITICAL" in result.stdout or "HIGH" in result.stdout


def test_cli_analyze_severity_filter(vulnerable_repo_path):
    result = runner.invoke(app, ["analyze", vulnerable_repo_path, "--severity", "high"])
    assert result.exit_code == 0
    assert "Codebase Analysis Report" in result.stdout


def test_cli_analyze_category_filter(vulnerable_repo_path):
    result = runner.invoke(app, ["analyze", vulnerable_repo_path, "--category", "security"])
    assert result.exit_code == 0
    assert "Codebase Analysis Report" in result.stdout
    assert "Security Findings" in result.stdout


def test_cli_analyze_json_flag(vulnerable_repo_path):
    result = runner.invoke(app, ["analyze", vulnerable_repo_path, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "findings" in data
    assert "summary" in data
    assert "files_analyzed" in data
    assert len(data["findings"]) > 0


def test_cli_analyze_export_json(vulnerable_repo_path, tmp_path):
    export_file = tmp_path / "findings_report.json"
    result = runner.invoke(app, ["analyze", vulnerable_repo_path, "--export-json", str(export_file)])
    assert result.exit_code == 0
    assert export_file.exists()
    
    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "findings_report" in data
    assert "findings" in data["findings_report"]
    assert "manifest" in data  # Backwards compatibility check
    assert "file_analyses" in data  # Backwards compatibility check


def test_cli_analyze_disable_categories(vulnerable_repo_path):
    result = runner.invoke(app, ["analyze", vulnerable_repo_path, "--no-security", "--no-patterns", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    categories = {f["category"] for f in data["findings"]}
    assert "SECURITY" not in categories
    assert "PATTERN" not in categories
