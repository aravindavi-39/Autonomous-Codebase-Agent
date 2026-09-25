"""Tests for RegressionVerifier: comparison rules and regression classification."""

import pytest

from sandbox.models import RegressionStatus, TestRun
from sandbox.verifier import RegressionVerifier


class TestRegressionVerifier:
    def test_both_runs_pass_yields_pass(self):
        verifier = RegressionVerifier()
        base = TestRun(status="PASSED", passed=10, failed=0, summary="10 passed")
        patch = TestRun(status="PASSED", passed=10, failed=0, summary="10 passed")
        comp = verifier.compare(base, patch)
        assert comp.regression_status == RegressionStatus.PASS
        assert "Zero regressions" in comp.summary

    def test_new_failure_yields_fail(self):
        verifier = RegressionVerifier()
        base = TestRun(status="PASSED", passed=10, failed=0, summary="10 passed")
        patch = TestRun(status="FAILED", passed=8, failed=2, summary="8 passed, 2 failed")
        comp = verifier.compare(base, patch)
        assert comp.regression_status == RegressionStatus.FAIL
        assert "REGRESSION DETECTED" in comp.summary

    def test_baseline_failure_classified_properly(self):
        verifier = RegressionVerifier()
        base = TestRun(status="FAILED", passed=8, failed=2, summary="8 passed, 2 failed")
        patch = TestRun(status="FAILED", passed=8, failed=2, summary="8 passed, 2 failed")
        comp = verifier.compare(base, patch)
        assert comp.regression_status == RegressionStatus.BASELINE_FAILURE
        assert "Baseline failure" in comp.summary

    def test_timeout_classified(self):
        verifier = RegressionVerifier()
        base = TestRun(status="PASSED", passed=10, failed=0)
        patch = TestRun(status="TIMEOUT", summary="timed out")
        comp = verifier.compare(base, patch)
        assert comp.regression_status == RegressionStatus.TEST_TIMEOUT

    def test_test_error_classified(self):
        verifier = RegressionVerifier()
        base = TestRun(status="PASSED", passed=10, failed=0)
        patch = TestRun(status="ERROR", summary="syntax crash")
        comp = verifier.compare(base, patch)
        assert comp.regression_status == RegressionStatus.TEST_ERROR

    def test_skipped_tests_flag(self):
        verifier = RegressionVerifier()
        comp = verifier.compare(None, None)
        assert comp.regression_status == RegressionStatus.SKIPPED
        assert "skipped" in comp.summary.lower()

    def test_no_tests_discovered(self):
        verifier = RegressionVerifier()
        base = TestRun(status="NO_TESTS")
        patch = TestRun(status="NO_TESTS")
        comp = verifier.compare(base, patch)
        assert comp.regression_status == RegressionStatus.NO_TESTS
