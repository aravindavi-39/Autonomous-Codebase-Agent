"""Tests for CLI apply command: approval boundary, safe enforcement, and execution."""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from cli.main import app
from sandbox.copier import compute_directory_fingerprint

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"
runner = CliRunner()


class TestCliApply:
    def test_apply_without_approve_is_rejected(self):
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        result = runner.invoke(app, ["apply", str(FIXTURE_DIR), "--finding", "PAT-003_65904b66"])
        assert result.exit_code == 1
        assert "Explicit approval is required" in result.output

        # Verify source remains untouched
        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after

    def test_apply_without_approve_json_output(self):
        result = runner.invoke(
            app,
            ["apply", str(FIXTURE_DIR), "--finding", "PAT-003_65904b66", "--json"],
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["session"]["approval_status"] == "REJECTED"
        assert any("explicit approval is required" in e.lower() for e in data["session"]["errors"])

    def test_apply_review_required_is_blocked(self):
        # In vulnerable_repo, PAT-002_... is a wildcard import (REVIEW_REQUIRED)
        # First retrieve finding ID for wildcard import
        from analysis.analyzer import RepositoryAnalyzer
        from analysis.findings.engine import AnalysisEngine
        from ingestion.pipeline import IngestionPipeline

        pipeline = IngestionPipeline()
        manifest = pipeline.ingest(str(FIXTURE_DIR))
        analyzer = RepositoryAnalyzer()
        index = analyzer.analyze_repository(str(FIXTURE_DIR), manifest=manifest)
        engine = AnalysisEngine()
        report = engine.analyze(manifest, index)

        wildcard_findings = [f for f in report.findings if f.type == "PAT-002"]
        if not wildcard_findings:
            pytest.skip("No PAT-002 finding in fixture")

        target_id = wildcard_findings[0].id
        result = runner.invoke(
            app,
            ["apply", str(FIXTURE_DIR), "--finding", target_id, "--approve", "--safe-only"],
        )
        assert result.exit_code == 1
        assert "Safety Error" in result.output or "safety tier" in result.output

    def test_apply_with_approve_safe_finding_in_sandbox(self):
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        result = runner.invoke(
            app,
            ["apply", str(FIXTURE_DIR), "--finding", "PAT-003_65904b66", "--approve"],
        )
        assert result.exit_code == 0
        assert "Sandbox Verification Report" in result.output
        assert "APPLIED" in result.output
        assert "UNCHANGED (Verified SHA-256 match)" in result.output

        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after

    def test_apply_with_approve_and_no_tests(self):
        result = runner.invoke(
            app,
            ["apply", str(FIXTURE_DIR), "--finding", "PAT-003_65904b66", "--approve", "--no-tests"],
        )
        assert result.exit_code == 0
        assert "SKIPPED" in result.output

    def test_apply_with_approve_json_mode(self):
        result = runner.invoke(
            app,
            ["apply", str(FIXTURE_DIR), "--finding", "PAT-003_65904b66", "--approve", "--no-tests", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["session"]["status"] in ("PASSED", "CLEANED")
        assert data["session"]["approval_status"] == "APPLIED_TO_SANDBOX"
        assert data["session"]["patch_result"]["success"] is True
