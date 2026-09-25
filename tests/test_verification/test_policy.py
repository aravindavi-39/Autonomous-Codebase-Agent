"""Tests for PolicyEvaluator: STRICT vs LENIENT, regression handling, and skipped check accounting."""

import pytest

from analysis.findings.models import Confidence, Finding, FindingCategory, Severity
from sandbox.models import RegressionStatus, TestComparison, TestRun
from verification.models import (
    FindingDelta,
    LintRunResult,
    LintSeverity,
    LintViolation,
    PolicyMode,
    VerificationPolicy,
    VerificationVerdict,
)
from verification.policy import PolicyEvaluator


def _sample_finding(fid: str) -> Finding:
    return Finding(
        id=fid,
        category=FindingCategory.PATTERN,
        type="PAT-003",
        severity=Severity.LOW,
        confidence=Confidence.HIGH,
        title="Sample",
        description="Sample",
        rationale="Sample",
        file="src/a.py",
        start_line=1,
        end_line=1,
        recommendation="Fix",
        analyzer_name="test",
    )


class TestPolicyEvaluator:
    def test_strict_passes_when_all_clean(self):
        evaluator = PolicyEvaluator()
        policy = VerificationPolicy.strict()
        delta = FindingDelta(
            target_finding_id="T1",
            target_existed_in_baseline=True,
            target_resolved=True,
            resolved_findings=[_sample_finding("T1")],
        )
        tc = TestComparison(regression_status=RegressionStatus.PASS, summary="Zero regressions")
        lr = LintRunResult(status="PASSED", error_count=0, warning_count=0)

        verdict, msgs, errs, warns = evaluator.evaluate(
            policy=policy,
            target_finding_id="T1",
            finding_delta=delta,
            test_comparison=tc,
            lint_run=lr,
        )
        assert verdict == VerificationVerdict.PASSED
        assert len(errs) == 0

    def test_fails_when_target_unresolved(self):
        evaluator = PolicyEvaluator()
        policy = VerificationPolicy.strict()
        delta = FindingDelta(
            target_finding_id="T1",
            target_existed_in_baseline=True,
            target_resolved=False,  # Unresolved!
            remaining_findings=[_sample_finding("T1")],
        )
        verdict, msgs, errs, warns = evaluator.evaluate(
            policy=policy,
            target_finding_id="T1",
            finding_delta=delta,
        )
        assert verdict == VerificationVerdict.FAILED
        assert any("still detected" in e.lower() for e in errs)

    def test_fails_when_new_findings_introduced(self):
        evaluator = PolicyEvaluator()
        policy = VerificationPolicy.strict()
        delta = FindingDelta(
            target_finding_id="T1",
            target_existed_in_baseline=True,
            target_resolved=True,
            new_findings=[_sample_finding("NEW_1")],  # New finding!
        )
        verdict, msgs, errs, warns = evaluator.evaluate(
            policy=policy,
            target_finding_id="T1",
            finding_delta=delta,
        )
        assert verdict == VerificationVerdict.FAILED
        assert any("new code finding" in e.lower() for e in errs)

    def test_fails_on_test_regression(self):
        evaluator = PolicyEvaluator()
        policy = VerificationPolicy.strict()
        tc = TestComparison(regression_status=RegressionStatus.FAIL, summary="2 tests failed")
        verdict, msgs, errs, warns = evaluator.evaluate(
            policy=policy,
            test_comparison=tc,
        )
        assert verdict == VerificationVerdict.FAILED
        assert any("test failure" in e.lower() for e in errs)

    def test_strict_vs_lenient_lint_warnings(self):
        evaluator = PolicyEvaluator()
        v = LintViolation(
            file="a.py", line=1, column=1, code="W291", message="Trailing ws", severity=LintSeverity.WARNING
        )
        lr = LintRunResult(status="WARNING", violations=[v], error_count=0, warning_count=1)

        # STRICT fails on warning
        strict_verdict, _, strict_errs, _ = evaluator.evaluate(
            policy=VerificationPolicy.strict(),
            lint_run=lr,
        )
        assert strict_verdict == VerificationVerdict.FAILED
        assert any("lint warning" in e.lower() for e in strict_errs)

        # LENIENT permits warning (yields WARNING verdict, not FAILED)
        lenient_verdict, _, lenient_errs, lenient_warns = evaluator.evaluate(
            policy=VerificationPolicy.lenient(),
            lint_run=lr,
        )
        assert lenient_verdict == VerificationVerdict.WARNING
        assert len(lenient_errs) == 0
        assert any("lint warning" in w.lower() for w in lenient_warns)

    def test_skipped_checks_explicitly_reported(self):
        evaluator = PolicyEvaluator()
        verdict, msgs, errs, warns = evaluator.evaluate(
            policy=VerificationPolicy.lenient(),
            test_skipped=True,
            lint_skipped=True,
        )
        assert any("test verification was explicitly skipped" in w.lower() for w in warns)
        assert any("linting was explicitly skipped" in w.lower() for w in warns)
