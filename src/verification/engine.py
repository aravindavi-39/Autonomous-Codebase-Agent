"""VerificationEngine: coordinates testing, linting, finding deltas, and policy verification."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from analysis.findings.engine import AnalysisEngine
from analysis.findings.models import Finding
from sandbox.copier import compute_directory_fingerprint
from sandbox.models import TestComparison, TestRun
from sandbox.tester import SandboxTester
from utils.logger import setup_logger
from verification.delta_engine import FindingDeltaEngine
from verification.linter import LintRunner
from verification.models import (
    FindingDelta,
    LintRunResult,
    VerificationPolicy,
    VerificationReport,
    VerificationVerdict,
)
from verification.policy import PolicyEvaluator

logger = setup_logger(__name__)


class VerificationEngine:
    """Consolidated engine for multi-tool code health verification and refactoring resolution audits."""

    def __init__(
        self,
        tester: Optional[SandboxTester] = None,
        linter: Optional[LintRunner] = None,
        delta_engine: Optional[FindingDeltaEngine] = None,
        policy_evaluator: Optional[PolicyEvaluator] = None,
    ) -> None:
        self.tester = tester or SandboxTester()
        self.linter = linter or LintRunner()
        self.delta_engine = delta_engine or FindingDeltaEngine()
        self.policy_evaluator = policy_evaluator or PolicyEvaluator()

    def verify_repository(
        self,
        repo_path: Path,
        target_finding_id: Optional[str] = None,
        policy: Optional[VerificationPolicy] = None,
        run_tests: bool = True,
        run_lint: bool = True,
        timeout_seconds: int = 30,
    ) -> VerificationReport:
        """Verify the health and finding state of a repository or sandbox in read-only mode."""
        resolved_repo = repo_path.resolve()
        now_iso = datetime.now(timezone.utc).isoformat()
        applied_policy = policy or VerificationPolicy.strict()

        # Step 0: Initial SHA-256 fingerprint
        fp_before = compute_directory_fingerprint(resolved_repo)

        # Step 1: Tests
        self.tester.timeout_seconds = timeout_seconds
        test_run: Optional[TestRun] = None
        if run_tests:
            logger.info("Executing test runner on %s...", resolved_repo)
            test_run = self.tester.run_tests(resolved_repo)

        # Step 2: Linting
        lint_run: Optional[LintRunResult] = None
        if run_lint:
            logger.info("Executing lint runner on %s...", resolved_repo)
            lint_run = self.linter.run(resolved_repo)

        # Step 3: Finding Analysis (if target finding specified)
        finding_delta: Optional[FindingDelta] = None
        if target_finding_id:
            logger.info("Running findings analysis to audit target %s...", target_finding_id)
            current_findings = self.delta_engine.analyze_repository_findings(resolved_repo)
            # When checking a standalone repo, we check if target finding is present
            target_present = any(f.id == target_finding_id for f in current_findings)
            finding_delta = FindingDelta(
                target_finding_id=target_finding_id,
                target_existed_in_baseline=target_present,
                target_resolved=not target_present,
                baseline_findings_count=len(current_findings),
                post_patch_findings_count=len(current_findings),
                remaining_findings=current_findings if target_present else [],
                summary=f"Audit for target finding '{target_finding_id}': {'PRESENT' if target_present else 'ABSENT'}",
            )

        # Step 4: Policy Evaluation
        verdict, messages, errors, warnings = self.policy_evaluator.evaluate(
            policy=applied_policy,
            target_finding_id=target_finding_id,
            finding_delta=finding_delta,
            test_run=test_run,
            test_skipped=not run_tests,
            lint_run=lint_run,
            lint_skipped=not run_lint,
        )

        # Step 5: Post-execution immutability verification
        fp_after = compute_directory_fingerprint(resolved_repo)
        source_intact = (fp_before == fp_after)
        if not source_intact:
            errors.append("CRITICAL: Repository content was modified during verification!")
            verdict = VerificationVerdict.FAILED

        return VerificationReport(
            repository=str(resolved_repo),
            timestamp=now_iso,
            verdict=verdict,
            policy=applied_policy,
            target_finding_id=target_finding_id,
            test_run=test_run,
            test_skipped=not run_tests,
            lint_run=lint_run,
            lint_skipped=not run_lint,
            finding_delta=finding_delta,
            source_fingerprint_before=fp_before,
            source_fingerprint_after=fp_after,
            source_intact=source_intact,
            messages=messages,
            errors=errors,
            warnings=warnings,
        )

    def audit_sandbox_refactoring(
        self,
        sandbox_path: Path,
        baseline_findings: list[Finding],
        target_finding_id: Optional[str] = None,
        test_comparison: Optional[TestComparison] = None,
        policy: Optional[VerificationPolicy] = None,
        run_lint: bool = True,
    ) -> VerificationReport:
        """Audit an applied patch inside a sandbox: evaluate finding resolution, new findings, and code health."""
        resolved_sandbox = sandbox_path.resolve()
        now_iso = datetime.now(timezone.utc).isoformat()
        applied_policy = policy or VerificationPolicy.strict()

        # 1. Re-analyze sandbox to get post-patch findings
        post_patch_findings = self.delta_engine.analyze_repository_findings(resolved_sandbox)

        # 2. Compute evidence-based finding delta
        finding_delta = self.delta_engine.compute_delta(
            baseline_findings=baseline_findings,
            post_patch_findings=post_patch_findings,
            target_finding_id=target_finding_id,
        )

        # 3. Linting on sandbox
        lint_run: Optional[LintRunResult] = None
        if run_lint:
            lint_run = self.linter.run(resolved_sandbox)

        # 4. Policy Evaluation
        verdict, messages, errors, warnings = self.policy_evaluator.evaluate(
            policy=applied_policy,
            target_finding_id=target_finding_id,
            finding_delta=finding_delta,
            test_comparison=test_comparison,
            test_skipped=(test_comparison is None),
            lint_run=lint_run,
            lint_skipped=not run_lint,
        )

        return VerificationReport(
            repository=str(resolved_sandbox),
            timestamp=now_iso,
            verdict=verdict,
            policy=applied_policy,
            target_finding_id=target_finding_id,
            test_comparison=test_comparison,
            test_skipped=(test_comparison is None),
            lint_run=lint_run,
            lint_skipped=not run_lint,
            finding_delta=finding_delta,
            messages=messages,
            errors=errors,
            warnings=warnings,
        )
