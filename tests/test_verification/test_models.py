"""Tests for verification models, serialization, and secret scrubbing."""

import json
import pytest

from verification.models import (
    FindingDelta,
    LintRunResult,
    LintSeverity,
    LintViolation,
    PolicyMode,
    VerificationPolicy,
    VerificationReport,
    VerificationVerdict,
)


class TestVerificationModels:
    def test_lint_severity_values(self):
        assert LintSeverity.ERROR.value == "ERROR"
        assert LintSeverity.WARNING.value == "WARNING"
        assert LintSeverity.INFO.value == "INFO"

    def test_verdict_values(self):
        assert VerificationVerdict.PASSED.value == "PASSED"
        assert VerificationVerdict.FAILED.value == "FAILED"
        assert VerificationVerdict.WARNING.value == "WARNING"
        assert VerificationVerdict.SKIPPED.value == "SKIPPED"
        assert VerificationVerdict.ERROR.value == "ERROR"

    def test_policy_strict_and_lenient_factories(self):
        strict_p = VerificationPolicy.strict()
        assert strict_p.mode == PolicyMode.STRICT
        assert strict_p.require_target_resolution is True
        assert strict_p.fail_on_lint_warnings is True
        assert strict_p.allow_new_findings is False

        lenient_p = VerificationPolicy.lenient()
        assert lenient_p.mode == PolicyMode.LENIENT
        assert lenient_p.fail_on_lint_warnings is False
        assert lenient_p.fail_on_lint_errors is True

    def test_lint_violation_and_run_result(self):
        v = LintViolation(
            file="src/sample.py",
            line=12,
            column=5,
            code="W291",
            message="Trailing whitespace",
            severity=LintSeverity.WARNING,
        )
        run_res = LintRunResult(
            status="WARNING",
            linter_name="ast_linter",
            violations=[v],
            files_checked=1,
            error_count=0,
            warning_count=1,
            summary="0 errors, 1 warning",
        )
        assert run_res.warning_count == 1
        assert run_res.violations[0].code == "W291"

    def test_verification_report_json_and_secret_redaction(self):
        report = VerificationReport(
            repository="/fake/repo",
            timestamp="2026-09-25T22:00:00Z",
            verdict=VerificationVerdict.PASSED,
            policy=VerificationPolicy.strict(),
            target_finding_id="PAT-003_123",
            messages=["api_key = 'FAKE_TEST_API_KEY_12345678901234567890'"],
            errors=["password = 'FAKE_TEST_PASSWORD_SECRET_123'"],
        )
        json_out = report.to_json()
        assert "FAKE_TEST_API_KEY_12345678901234567890" not in json_out
        assert "FAKE_TEST_PASSWORD_SECRET_123" not in json_out
        assert "[REDACTED_SECRET]" in json_out

        data = json.loads(json_out)
        assert data["verdict"] == "PASSED"
        assert data["repository"] == "/fake/repo"

    def test_verification_report_format_cli(self):
        report = VerificationReport(
            repository="/test/repo",
            timestamp="2026-09-25T22:00:00Z",
            verdict=VerificationVerdict.PASSED,
            policy=VerificationPolicy.strict(),
            target_finding_id="PAT-003_abc",
            finding_delta=FindingDelta(
                target_finding_id="PAT-003_abc",
                target_existed_in_baseline=True,
                target_resolved=True,
                baseline_findings_count=1,
                post_patch_findings_count=0,
                summary="Target resolved",
            ),
            test_skipped=True,
            lint_skipped=True,
        )
        cli_out = report.format_cli()
        assert "Verification & Audit Report" in cli_out
        assert "Target Finding:        PAT-003_abc" in cli_out
        assert "Target Resolved:       YES (Confirmed eliminated)" in cli_out
        assert "Test Suite:            SKIPPED (--no-tests)" in cli_out
        assert "Lint & Syntax:         SKIPPED (--no-lint)" in cli_out
