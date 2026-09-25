"""Tests for the CLI analyze command."""

import json
from pathlib import Path
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


class TestCLIAnalyzeCommand:
    """Verify CLI analyze command execution and formatting."""

    def test_analyze_sample_repo(self) -> None:
        sample_repo = str(Path("tests/fixtures/sample_repo"))
        result = runner.invoke(app, ["analyze", sample_repo])
        assert result.exit_code == 0
        assert "Repository: sample_repo" in result.output
        assert "Python Files" in result.output
        assert "Classes" in result.output
        assert "Functions" in result.output
        assert "Methods" in result.output
        assert "Imports" in result.output
        assert "Calls" in result.output
        assert "User" in result.output
        assert "create_app" in result.output

    def test_analyze_with_export_json(self, tmp_path: Path) -> None:
        sample_repo = str(Path("tests/fixtures/sample_repo"))
        out_json = tmp_path / "analysis_out.json"
        result = runner.invoke(app, ["analyze", sample_repo, "--export-json", str(out_json)])
        assert result.exit_code == 0
        assert out_json.exists()

        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert "manifest" in data
        assert "file_analyses" in data
        assert "summary" in data
        assert data["summary"]["python_files_analyzed"] == 7

    def test_analyze_invalid_path(self) -> None:
        result = runner.invoke(app, ["analyze", "/nonexistent/repo/dir"])
        assert result.exit_code == 1
        assert "Error:" in result.output
