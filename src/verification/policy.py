"""Deterministic verification policy evaluation (STRICT vs. LENIENT)."""

from __future__ import annotations

from typing import Optional

from sandbox.models import RegressionStatus, TestComparison, TestRun
from verification.models import (
    FindingDelta,
    LintRunResult,
    PolicyMode,
    VerificationPolicy,
    VerificationVerdict,
)


class PolicyEvaluator:
    """Evaluates consolidated verification results against a deterministic policy."""

    def evaluate(
        self,
        policy: VerificationPolicy,
        target_finding_id: Optional[str] = None,
        finding_delta: Optional[FindingDelta] = None,
        test_comparison: Optional[TestComparison] = None,
        test_run: Optional[TestRun] = None,
        test_skipped: bool = False,
        lint_run: Optional[LintRunResult] = None,
        lint_skipped: bool = False,
    ) -> tuple[VerificationVerdict, list[str], list[str], list[str]]:
        """Evaluate verification results against the given policy.

        Returns:
            Tuple of (verdict, summary_messages, errors, warnings).
        """
        messages: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Target Finding Resolution Gate
        if target_finding_id and policy.require_target_resolution:
            if not finding_delta:
                errors.append(f"Target finding '{target_finding_id}' requested, but no finding delta analysis was performed.")
            elif not finding_delta.target_existed_in_baseline:
                errors.append(
                    f"Target finding '{target_finding_id}' was not detected in baseline analysis. "
                    "Cannot verify resolution of an unobserved finding."
                )
            elif not finding_delta.target_resolved:
                errors.append(
                    f"Target finding '{target_finding_id}' still detected after patch application. "
                    "Refactoring failed to eliminate the target problem."
                )
            else:
                messages.append(f"Target finding '{target_finding_id}' confirmed eliminated.")

        # 2. Genuinely New Findings Gate
        if finding_delta:
            if finding_delta.new_findings and not policy.allow_new_findings:
                new_count = len(finding_delta.new_findings)
                errors.append(
                    f"Refactoring introduced {new_count} new code finding(s) not present in baseline."
                )
                for nf in finding_delta.new_findings[:5]:
                    errors.append(f"  • [{nf.type}] {nf.file}:{nf.start_line} - {nf.title}")
            elif not finding_delta.new_findings:
                messages.append("Zero new code smells or security findings introduced.")

        # 3. Test Suite Regression Gate
        if test_skipped:
            warnings.append("Test verification was explicitly skipped (--no-tests).")
        elif test_comparison:
            reg_status = test_comparison.regression_status
            if reg_status == RegressionStatus.PASS:
                messages.append("Test suite passed with zero regressions.")
            elif reg_status == RegressionStatus.NO_TESTS:
                messages.append("No test suite present in repository.")
            elif reg_status == RegressionStatus.BASELINE_FAILURE:
                warnings.append(test_comparison.summary)
            elif reg_status in (RegressionStatus.FAIL, RegressionStatus.TEST_TIMEOUT, RegressionStatus.TEST_ERROR):
                if policy.require_zero_test_regressions:
                    errors.append(f"Test failure: {test_comparison.summary}")
                else:
                    warnings.append(f"Test warning: {test_comparison.summary}")
        elif test_run:
            if test_run.status == "PASSED":
                messages.append(f"Tests passed ({test_run.summary}).")
            elif test_run.status == "NO_TESTS":
                messages.append("No tests found.")
            elif policy.require_zero_test_regressions:
                errors.append(f"Tests failed ({test_run.summary}).")

        # 4. Lint and Syntax Gate
        if lint_skipped:
            warnings.append("Linting was explicitly skipped (--no-lint).")
        elif lint_run:
            if lint_run.error_count > 0 and policy.fail_on_lint_errors:
                errors.append(f"Linting failed with {lint_run.error_count} fatal error(s) / syntax violation(s).")
                for v in lint_run.violations:
                    if v.severity.value == "ERROR":
                        errors.append(f"  • {v.file}:{v.line} [{v.code}] {v.message}")
            elif lint_run.warning_count > 0:
                if policy.fail_on_lint_warnings:
                    errors.append(f"Strict policy failed on {lint_run.warning_count} lint warning(s).")
                else:
                    warnings.append(f"Lenient policy: permitted {lint_run.warning_count} non-fatal lint warning(s).")
            else:
                messages.append("Code passed static lint and syntax checks with zero violations.")

        # 5. Compute Final Verdict
        if errors:
            verdict = VerificationVerdict.FAILED
        elif warnings:
            verdict = VerificationVerdict.WARNING
        else:
            verdict = VerificationVerdict.PASSED

        return verdict, messages, errors, warnings
