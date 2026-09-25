"""Tests for repository immutability during verification engine operations."""

from pathlib import Path
import pytest

from sandbox.copier import compute_directory_fingerprint
from verification.engine import VerificationEngine
from verification.models import VerificationPolicy

FIXTURE_VULN = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"
FIXTURE_SBX = Path(__file__).resolve().parent.parent / "fixtures" / "sandbox_test_repo"


class TestVerificationImmutability:
    def test_vulnerable_repo_strictly_immutable_during_verify(self):
        fp_before = compute_directory_fingerprint(FIXTURE_VULN)
        engine = VerificationEngine()

        report = engine.verify_repository(
            repo_path=FIXTURE_VULN,
            policy=VerificationPolicy.lenient(),
            run_tests=True,
            run_lint=True,
        )

        fp_after = compute_directory_fingerprint(FIXTURE_VULN)
        assert fp_before == fp_after, "vulnerable_repo was modified during verify!"
        assert report.source_intact is True

    def test_sandbox_test_repo_strictly_immutable_during_verify(self):
        fp_before = compute_directory_fingerprint(FIXTURE_SBX)
        engine = VerificationEngine()

        report = engine.verify_repository(
            repo_path=FIXTURE_SBX,
            policy=VerificationPolicy.lenient(),
            run_tests=True,
            run_lint=True,
        )

        fp_after = compute_directory_fingerprint(FIXTURE_SBX)
        assert fp_before == fp_after, "sandbox_test_repo was modified during verify!"
        assert report.source_intact is True
