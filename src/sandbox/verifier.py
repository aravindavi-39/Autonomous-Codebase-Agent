"""RegressionVerifier: compares baseline and post-patch test results to detect regressions."""

from __future__ import annotations

from typing import Optional

from sandbox.models import RegressionStatus, TestComparison, TestRun
from utils.logger import setup_logger

logger = setup_logger(__name__)


class RegressionVerifier:
    """Evaluates test runs before and after patch application to detect regressions."""

    def compare(
        self,
        baseline_run: Optional[TestRun],
        patched_run: Optional[TestRun],
    ) -> TestComparison:
        """Compare baseline and post-patch test results.

        Args:
            baseline_run: Test results before patch.
            patched_run: Test results after patch.

        Returns:
            A TestComparison object with regression status and summary.
        """
        if baseline_run is None and patched_run is None:
            return TestComparison(
                baseline_run=None,
                patched_run=None,
                regression_status=RegressionStatus.SKIPPED,
                summary="Test verification skipped by user request (--no-tests).",
            )

        if (baseline_run and baseline_run.status == "NO_TESTS") or (patched_run and patched_run.status == "NO_TESTS"):
            return TestComparison(
                baseline_run=baseline_run,
                patched_run=patched_run,
                regression_status=RegressionStatus.NO_TESTS,
                summary="No test suite discovered in repository.",
            )

        if not baseline_run or not patched_run:
            return TestComparison(
                baseline_run=baseline_run,
                patched_run=patched_run,
                regression_status=RegressionStatus.TEST_ERROR,
                summary="Incomplete test runs; comparison unavailable.",
            )

        # 1. Baseline Failure Check
        if baseline_run.status == "FAILED" or baseline_run.failed > 0:
            return TestComparison(
                baseline_run=baseline_run,
                patched_run=patched_run,
                regression_status=RegressionStatus.BASELINE_FAILURE,
                summary=(
                    f"Baseline failure: test suite had {baseline_run.failed} failing test(s) "
                    "prior to patch application. Refactoring did not cause pre-existing failures."
                ),
            )

        # 2. Timeout and Error Checks
        if patched_run.status == "TIMEOUT":
            return TestComparison(
                baseline_run=baseline_run,
                patched_run=patched_run,
                regression_status=RegressionStatus.TEST_TIMEOUT,
                summary="Post-patch test execution timed out.",
            )

        if patched_run.status == "ERROR":
            return TestComparison(
                baseline_run=baseline_run,
                patched_run=patched_run,
                regression_status=RegressionStatus.TEST_ERROR,
                summary=f"Post-patch test execution encountered an error: {patched_run.summary}",
            )

        # 3. Regression Evaluation
        if patched_run.failed > 0:
            return TestComparison(
                baseline_run=baseline_run,
                patched_run=patched_run,
                regression_status=RegressionStatus.FAIL,
                summary=(
                    f"REGRESSION DETECTED: {patched_run.failed} test(s) failed after patch "
                    f"application (baseline had {baseline_run.failed} failures)."
                ),
            )

        # 4. Clean Pass
        return TestComparison(
            baseline_run=baseline_run,
            patched_run=patched_run,
            regression_status=RegressionStatus.PASS,
            summary=f"PASS: All {patched_run.passed} tests passed. Zero regressions detected.",
        )
