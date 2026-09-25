"""Tests for SandboxManager: lifecycle orchestration, approval gate, and immutability verification."""

from pathlib import Path
import pytest

from refactoring.models import ChangeProposal, FileChange, SafetyClassification, TextEdit
from sandbox.copier import compute_directory_fingerprint
from sandbox.manager import SandboxManager
from sandbox.models import ApprovalStatus, RegressionStatus, SandboxStatus

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sandbox_test_repo"


def _make_safe_proposal():
    # Targets calculator.py line 6: def add_entry(val, history=[]):
    lines = (FIXTURE_DIR / "src" / "calculator.py").read_text(encoding="utf-8").splitlines()
    orig_sig = lines[5]  # line 6
    orig_body = lines[7]  # line 8: history.append(val)
    
    edit1 = TextEdit(
        start_line=6,
        end_line=6,
        original_text=orig_sig,
        replacement_text="def add_entry(val, history=None):",
    )
    edit2 = TextEdit(
        start_line=8,
        end_line=8,
        original_text=orig_body,
        replacement_text="    if history is None:\n        history = []\n" + orig_body,
    )
    return ChangeProposal(
        finding_id="PAT-003_calc",
        finding_type="PAT-003",
        strategy="MutableDefaultStrategy",
        safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
        file_changes=[FileChange(file_path="src/calculator.py", edits=[edit1, edit2])],
        description="Fix mutable default argument in add_entry",
        rationale="State leakage prevention",
        source_file="src/calculator.py",
        source_start_line=6,
        source_end_line=8,
    )


class TestSandboxManager:
    def test_manager_rejects_unapproved_session(self):
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        manager = SandboxManager()
        proposal = _make_safe_proposal()

        report = manager.execute_session(
            source_path=FIXTURE_DIR,
            proposal=proposal,
            approved=False,  # Unapproved!
        )

        assert report.session.approval_status == ApprovalStatus.REJECTED
        assert report.session.status == SandboxStatus.ERROR
        assert any("explicit approval is required" in err.lower() for err in report.session.errors)

        # Immutability check
        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after
        assert report.session.source_intact is True

    def test_manager_rejects_review_required_proposal(self):
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        manager = SandboxManager()
        proposal = ChangeProposal(
            finding_id="PAT-001_review",
            finding_type="PAT-001",
            strategy="BroadExceptionStrategy",
            safety=SafetyClassification.REVIEW_REQUIRED,
            file_changes=[],
            description="Broad except",
            rationale="Review",
            source_file="src/calculator.py",
            source_start_line=1,
            source_end_line=1,
        )

        report = manager.execute_session(
            source_path=FIXTURE_DIR,
            proposal=proposal,
            approved=True,
        )

        assert report.session.status == SandboxStatus.ERROR
        assert any("safety tier" in err.lower() for err in report.session.errors)

        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after
        assert report.session.source_intact is True

    def test_manager_successful_safe_session_with_tests(self):
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        manager = SandboxManager()
        proposal = _make_safe_proposal()

        report = manager.execute_session(
            source_path=FIXTURE_DIR,
            proposal=proposal,
            approved=True,
            run_tests=True,
            keep_sandbox=False,
        )

        session = report.session
        assert session.status in (SandboxStatus.PASSED, SandboxStatus.CLEANED)
        assert session.approval_status == ApprovalStatus.APPLIED_TO_SANDBOX
        assert session.patch_result is not None
        assert session.patch_result.success is True

        # Test verification checks
        assert session.test_comparison is not None
        assert session.test_comparison.regression_status == RegressionStatus.PASS
        assert session.test_comparison.baseline_run.passed == 2
        assert session.test_comparison.patched_run.passed == 2
        assert session.cleaned_up is True

        # Source immutability check
        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after
        assert session.source_intact is True

    def test_manager_keep_sandbox_flag(self):
        manager = SandboxManager()
        proposal = _make_safe_proposal()

        report = manager.execute_session(
            source_path=FIXTURE_DIR,
            proposal=proposal,
            approved=True,
            run_tests=False,
            keep_sandbox=True,
        )

        session = report.session
        assert session.cleaned_up is False
        assert Path(session.sandbox_path).exists()

        # Clean up manually after test
        manager.cleanup.cleanup(Path(session.sandbox_path))
        assert not Path(session.sandbox_path).exists()

    def test_manager_no_tests_flag(self):
        manager = SandboxManager()
        proposal = _make_safe_proposal()

        report = manager.execute_session(
            source_path=FIXTURE_DIR,
            proposal=proposal,
            approved=True,
            run_tests=False,  # Skip tests
            keep_sandbox=False,
        )

        session = report.session
        assert session.test_comparison.regression_status == RegressionStatus.SKIPPED
        assert session.patch_result.success is True
