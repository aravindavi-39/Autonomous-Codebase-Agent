"""Tests for the CLI graph command."""

import json
from pathlib import Path
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


class TestCLIGraphCommand:
    """Verify CLI graph command execution, table formatting, and JSON export."""

    def test_graph_sample_repo(self) -> None:
        sample_repo = str(Path("tests/fixtures/sample_repo"))
        result = runner.invoke(app, ["graph", sample_repo])
        assert result.exit_code == 0
        assert "Repository: sample_repo" in result.output
        assert "Nodes" in result.output
        assert "Edges" in result.output
        assert "Relationships" in result.output
        assert "IMPORTS" in result.output
        assert "DEFINES" in result.output
        assert "CALLS" in result.output
        assert "CONTAINS" in result.output
        assert "TESTS" in result.output
        assert "Dependency hotspots" in result.output
        assert "Circular dependencies" in result.output

    def test_graph_with_export_json(self, tmp_path: Path) -> None:
        sample_repo = str(Path("tests/fixtures/sample_repo"))
        out_json = tmp_path / "graph_out.json"
        result = runner.invoke(app, ["graph", sample_repo, "--export-json", str(out_json)])
        assert result.exit_code == 0
        assert out_json.exists()

        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert "nodes" in data
        assert "edges" in data
        assert "statistics" in data
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0

        # Check edge has required fields: source, target, type, file, line
        first_edge = data["edges"][0]
        assert "source" in first_edge
        assert "target" in first_edge
        assert "type" in first_edge
        assert "file" in first_edge
        assert "line" in first_edge

    def test_graph_invalid_path(self) -> None:
        result = runner.invoke(app, ["graph", "/nonexistent/repo/dir"])
        assert result.exit_code == 1
        assert "Error:" in result.output
