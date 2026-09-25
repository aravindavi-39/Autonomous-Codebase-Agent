"""Tests for VerificationEngine: repository verification, sandbox refactoring audits, and immutability."""

from pathlib import Path
import pytest

from sandbox.copier import SandboxCopier, compute_directory_fingerprint
from sandbox.patcher import SandboxPatcher
from verification.delta_engine import FindingDeltaEngine
from verification.engine import VerificationEngine
from verification.models import VerificationPolicy, VerificationVerdict

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sandbox_test_repo"


class TestVerificationEngine:
    def test_verify_repository_clean(self):
        engine = VerificationEngine()
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        
        report = engine.verify_repository(
            repo_path=FIXTURE_DIR,
            policy=VerificationPolicy.lenient(),
            run_tests=True,
            run_lint=True,
        )

        assert report.verdict in (VerificationVerdict.PASSED, VerificationVerdict.WARNING)
        assert report.test_run is not None
        assert report.test_run.passed == 2
        assert report.lint_run is not None
        assert report.source_intact is True

        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after

    def test_audit_sandbox_refactoring_detects_target_resolution(self, tmp_path):
        copier = SandboxCopier(temp_base_dir=tmp_path)
        sandbox_path = copier.create_sandbox(FIXTURE_DIR, "engine_audit_test")

        delta_engine = FindingDeltaEngine()
        baseline_findings = delta_engine.analyze_repository_findings(sandbox_path)

        # Locate mutable default finding PAT-003
        pat003_findings = [f for f in baseline_findings if f.type == "PAT-003"]
        assert len(pat003_findings) > 0
        target = pat003_findings[0]

        # Patch the file inside sandbox to fix mutable default, preserving docstring
        calc_file = sandbox_path / "src" / "calculator.py"
        content = calc_file.read_text(encoding="utf-8")
        fixed_content = content.replace(
            "def add_entry(val, history=[]):",
            "def add_entry(val, history=None):",
        ).replace(
            '    """Function with a mutable default argument and unused import sys."""\n    history.append(val)',
            '    """Function with a mutable default argument and unused import sys."""\n    if history is None:\n        history = []\n    history.append(val)',
        )
        calc_file.write_text(fixed_content, encoding="utf-8")

        engine = VerificationEngine()
        report = engine.audit_sandbox_refactoring(
            sandbox_path=sandbox_path,
            baseline_findings=baseline_findings,
            target_finding_id=target.id,
            policy=VerificationPolicy.lenient(),
            run_lint=True,
        )

        assert report.finding_delta is not None
        assert report.finding_delta.target_resolved is True
        assert any(f.type == "PAT-003" for f in report.finding_delta.resolved_findings)
        assert len(report.finding_delta.new_findings) == 0

    def test_audit_sandbox_refactoring_detects_newly_introduced_finding(self, tmp_path):
        copier = SandboxCopier(temp_base_dir=tmp_path)
        sandbox_path = copier.create_sandbox(FIXTURE_DIR, "engine_new_finding_test")

        delta_engine = FindingDeltaEngine()
        baseline_findings = delta_engine.analyze_repository_findings(sandbox_path)

        # Introduce a new smell/pattern (wildcard import PAT-002)
        calc_file = sandbox_path / "src" / "calculator.py"
        content = calc_file.read_text(encoding="utf-8")
        corrupted_content = "from os import *\n" + content
        calc_file.write_text(corrupted_content, encoding="utf-8")

        engine = VerificationEngine()
        report = engine.audit_sandbox_refactoring(
            sandbox_path=sandbox_path,
            baseline_findings=baseline_findings,
            policy=VerificationPolicy.strict(),
            run_lint=True,
        )

        assert report.finding_delta is not None
        assert len(report.finding_delta.new_findings) > 0
        assert any(f.type == "PAT-002" for f in report.finding_delta.new_findings)
        assert report.verdict == VerificationVerdict.FAILED
        assert any("new code finding" in e.lower() for e in report.errors)
