"""SandboxManager: orchestrates isolated repository copying, patch application, testing, and cleanup."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from refactoring.models import ChangeProposal, SafetyClassification
from sandbox.cleanup import SandboxCleanup
from sandbox.copier import SandboxCopier, compute_directory_fingerprint
from sandbox.models import (
    ApprovalStatus,
    PatchApplicationResult,
    RegressionStatus,
    SandboxReport,
    SandboxSession,
    SandboxStatus,
    TestComparison,
)
from sandbox.patcher import SandboxPatcher
from sandbox.tester import SandboxTester
from sandbox.verifier import RegressionVerifier
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SandboxManager:
    """Manages the full lifecycle of an isolated sandbox session."""

    def __init__(
        self,
        copier: SandboxCopier | None = None,
        patcher: SandboxPatcher | None = None,
        tester: SandboxTester | None = None,
        verifier: RegressionVerifier | None = None,
        cleanup: SandboxCleanup | None = None,
        verification_engine: Any | None = None,
    ) -> None:
        self.copier = copier or SandboxCopier()
        self.patcher = patcher or SandboxPatcher()
        self.tester = tester or SandboxTester()
        self.verifier = verifier or RegressionVerifier()
        self.cleanup = cleanup or SandboxCleanup()
        self.verification_engine = verification_engine

    def execute_session(
        self,
        source_path: Path,
        proposal: ChangeProposal,
        approved: bool = False,
        run_tests: bool = True,
        keep_sandbox: bool = False,
        timeout_seconds: int = 30,
        baseline_findings: list[Any] | None = None,
        audit_verification: bool = False,
    ) -> SandboxReport:
        """Execute a full sandbox session with strict approval and safety checks.

        Args:
            source_path: Path to the target local repository (read-only).
            proposal: The change proposal to apply and verify.
            approved: Mandatory flag indicating explicit human approval.
            run_tests: If True, execute baseline and post-patch tests.
            keep_sandbox: If True, retain the sandbox directory after testing.
            timeout_seconds: Maximum seconds allowed for each test run.

        Returns:
            SandboxReport detailing session outcome and regression status.
        """
        resolved_source = source_path.resolve()
        session_id = uuid.uuid4().hex[:12]
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 0: Initial Source Repository Fingerprint (Pre-execution)
        source_fp_before = compute_directory_fingerprint(resolved_source)

        # Step 1: Mandatory Human Approval Check
        if not approved:
            logger.warning("Sandbox application attempted without explicit approval.")
            session = SandboxSession(
                id=session_id,
                source_repository=str(resolved_source),
                source_fingerprint_before=source_fp_before,
                source_fingerprint_after=source_fp_before,
                sandbox_path="",
                status=SandboxStatus.ERROR,
                approval_status=ApprovalStatus.REJECTED,
                created_at=now_iso,
                finding_id=proposal.finding_id,
                proposal_id=proposal.finding_id,
                strategy_name=proposal.strategy,
                safety_classification=proposal.safety.value,
                cleaned_up=True,
                errors=["Explicit approval is required before applying this proposal to a sandbox."],
            )
            return SandboxReport(session=session)

        # Step 2: Strict Safety Tier Enforcement
        if proposal.safety != SafetyClassification.SAFE_AUTOMATIC_PROPOSAL:
            logger.warning(
                "Proposal %s has safety classification %s; application rejected.",
                proposal.finding_id,
                proposal.safety.value,
            )
            session = SandboxSession(
                id=session_id,
                source_repository=str(resolved_source),
                source_fingerprint_before=source_fp_before,
                source_fingerprint_after=source_fp_before,
                sandbox_path="",
                status=SandboxStatus.ERROR,
                approval_status=ApprovalStatus.APPROVED,
                created_at=now_iso,
                finding_id=proposal.finding_id,
                proposal_id=proposal.finding_id,
                strategy_name=proposal.strategy,
                safety_classification=proposal.safety.value,
                cleaned_up=True,
                errors=[
                    f"Proposal '{proposal.finding_id}' has safety tier '{proposal.safety.value}'. "
                    "Only 'SAFE_AUTOMATIC_PROPOSAL' can be applied to a sandbox."
                ],
            )
            return SandboxReport(session=session)

        # Step 3: Create Physically Isolated Sandbox Copy
        errors: list[str] = []
        warnings: list[str] = []
        sandbox_repo_dir: Path | None = None

        try:
            sandbox_repo_dir = self.copier.create_sandbox(resolved_source, session_id)
        except Exception as exc:
            logger.error("Failed to create sandbox copy: %s", exc)
            session = SandboxSession(
                id=session_id,
                source_repository=str(resolved_source),
                source_fingerprint_before=source_fp_before,
                source_fingerprint_after=compute_directory_fingerprint(resolved_source),
                sandbox_path="",
                status=SandboxStatus.ERROR,
                approval_status=ApprovalStatus.APPROVED,
                created_at=now_iso,
                finding_id=proposal.finding_id,
                proposal_id=proposal.finding_id,
                strategy_name=proposal.strategy,
                safety_classification=proposal.safety.value,
                cleaned_up=True,
                errors=[f"Failed to create sandbox: {exc}"],
            )
            return SandboxReport(session=session)

        # Step 4: Baseline Test Execution (Pre-patch)
        self.tester.timeout_seconds = timeout_seconds
        baseline_run = None
        if run_tests:
            logger.info("Executing baseline test suite inside sandbox...")
            baseline_run = self.tester.run_tests(sandbox_repo_dir)

        # Step 5: Patch Application
        logger.info("Applying proposed patch inside sandbox...")
        patch_result = self.patcher.apply_proposal(proposal, sandbox_repo_dir)
        if not patch_result.success:
            errors.extend(patch_result.errors)

        # Step 6: Post-Patch Test Execution
        patched_run = None
        if run_tests and patch_result.success:
            logger.info("Executing post-patch test suite inside sandbox...")
            patched_run = self.tester.run_tests(sandbox_repo_dir)

        # Step 7: Regression Comparison
        test_comp = self.verifier.compare(baseline_run, patched_run)
        if run_tests:
            if test_comp.regression_status == RegressionStatus.FAIL:
                errors.append(f"Regression detected: {test_comp.summary}")
            elif test_comp.regression_status == RegressionStatus.BASELINE_FAILURE:
                warnings.append(test_comp.summary)

        # Step 7.5: Modular Verification Audit (Finding Resolution & New Findings)
        verification_dict: dict[str, Any] | None = None
        if audit_verification and sandbox_repo_dir and patch_result.success:
            logger.info("Executing modular verification audit on patched sandbox...")
            from verification.engine import VerificationEngine
            v_engine = self.verification_engine or VerificationEngine(tester=self.tester)
            v_report = v_engine.audit_sandbox_refactoring(
                sandbox_path=sandbox_repo_dir,
                baseline_findings=baseline_findings or [],
                target_finding_id=proposal.finding_id,
                test_comparison=test_comp,
            )
            verification_dict = v_report.model_dump(mode="json")
            if v_report.verdict.value == "FAILED":
                errors.extend(v_report.errors)
            warnings.extend(v_report.warnings)

        # Determine overall session status
        if not patch_result.success:
            session_status = SandboxStatus.FAILED
        elif test_comp and test_comp.regression_status == RegressionStatus.FAIL:
            session_status = SandboxStatus.FAILED
        elif errors:
            session_status = SandboxStatus.FAILED
        else:
            session_status = SandboxStatus.PASSED

        # Step 8: Verify Original Repository Remains 100% Intact
        source_fp_after = compute_directory_fingerprint(resolved_source)
        if source_fp_before != source_fp_after:
            critical_msg = "CRITICAL VIOLATION: Source repository was modified during sandbox session!"
            logger.critical(critical_msg)
            errors.append(critical_msg)
            session_status = SandboxStatus.ERROR

        # Step 9: Sandbox Cleanup
        cleaned = False
        if not keep_sandbox and sandbox_repo_dir:
            cleaned = self.cleanup.cleanup(sandbox_repo_dir)
            if cleaned and session_status == SandboxStatus.PASSED:
                session_status = SandboxStatus.CLEANED

        session = SandboxSession(
            id=session_id,
            source_repository=str(resolved_source),
            source_fingerprint_before=source_fp_before,
            source_fingerprint_after=source_fp_after,
            sandbox_path=str(sandbox_repo_dir) if sandbox_repo_dir else "",
            status=session_status,
            approval_status=ApprovalStatus.APPLIED_TO_SANDBOX if patch_result.success else ApprovalStatus.APPROVED,
            created_at=now_iso,
            finding_id=proposal.finding_id,
            proposal_id=proposal.finding_id,
            strategy_name=proposal.strategy,
            safety_classification=proposal.safety.value,
            patch_result=patch_result,
            test_comparison=test_comp,
            verification_report=verification_dict,
            cleaned_up=cleaned,
            errors=errors,
            warnings=warnings + patch_result.warnings,
        )

        return SandboxReport(session=session)
