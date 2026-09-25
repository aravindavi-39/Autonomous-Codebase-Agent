"""Tests for sandbox models, status transitions, and secret scrubbing."""

import json
import pytest

from sandbox.models import (
    ApprovalStatus,
    PatchApplicationResult,
    RegressionStatus,
    SandboxReport,
    SandboxSession,
    SandboxStatus,
    TestComparison,
    TestRun,
    redact_secrets,
)


class TestSandboxEnums:
    def test_sandbox_status_values(self):
        assert SandboxStatus.CREATED.value == "CREATED"
        assert SandboxStatus.PATCHED.value == "PATCHED"
        assert SandboxStatus.TESTING.value == "TESTING"
        assert SandboxStatus.PASSED.value == "PASSED"
        assert SandboxStatus.FAILED.value == "FAILED"
        assert SandboxStatus.CLEANED.value == "CLEANED"
        assert SandboxStatus.ERROR.value == "ERROR"

    def test_approval_status_values(self):
        assert ApprovalStatus.PROPOSED.value == "PROPOSED"
        assert ApprovalStatus.APPROVED.value == "APPROVED"
        assert ApprovalStatus.REJECTED.value == "REJECTED"
        assert ApprovalStatus.APPLIED_TO_SANDBOX.value == "APPLIED_TO_SANDBOX"
        assert ApprovalStatus.VERIFIED.value == "VERIFIED"

    def test_regression_status_values(self):
        assert RegressionStatus.PASS.value == "PASS"
        assert RegressionStatus.FAIL.value == "FAIL"
        assert RegressionStatus.BASELINE_FAILURE.value == "BASELINE_FAILURE"
        assert RegressionStatus.TEST_TIMEOUT.value == "TEST_TIMEOUT"
        assert RegressionStatus.TEST_ERROR.value == "TEST_ERROR"
        assert RegressionStatus.SYNTAX_ERROR.value == "SYNTAX_ERROR"
        assert RegressionStatus.NO_TESTS.value == "NO_TESTS"
        assert RegressionStatus.SKIPPED.value == "SKIPPED"


class TestSecretScrubbing:
    def test_redact_secrets_cleans_credentials(self):
        text = "api_key = 'FAKE_TEST_API_KEY_12345678901234567890'\npassword = 'FAKE_TEST_PASSWORD_SECRET_123'"
        cleaned = redact_secrets(text)
        assert "FAKE_TEST_API_KEY_12345678901234567890" not in cleaned
        assert "FAKE_TEST_PASSWORD_SECRET_123" not in cleaned
        assert "[REDACTED_SECRET]" in cleaned

    def test_redact_secrets_handles_empty(self):
        assert redact_secrets("") == ""
        assert redact_secrets(None) is None


class TestSandboxSessionAndReport:
    def _create_sample_session(self, fp_before="abc", fp_after="abc"):
        return SandboxSession(
            id="test_session_123",
            source_repository="/fake/repo",
            source_fingerprint_before=fp_before,
            source_fingerprint_after=fp_after,
            sandbox_path="/tmp/codebase_agent_sandbox_123/repo",
            status=SandboxStatus.PASSED,
            approval_status=ApprovalStatus.APPROVED,
            created_at="2026-09-25T22:00:00Z",
            finding_id="PAT-003_123",
            strategy_name="MutableDefaultStrategy",
            safety_classification="SAFE_AUTOMATIC_PROPOSAL",
            patch_result=PatchApplicationResult(
                success=True,
                finding_id="PAT-003_123",
                strategy="MutableDefaultStrategy",
                applied_files=["src/foo.py"],
                diff_applied="--- a/src/foo.py\n+++ b/src/foo.py\n",
            ),
            test_comparison=TestComparison(
                baseline_run=TestRun(summary="5 passed in 0.2s"),
                patched_run=TestRun(summary="5 passed in 0.2s"),
                regression_status=RegressionStatus.PASS,
                summary="All tests passed.",
            ),
            cleaned_up=True,
        )

    def test_source_intact_property(self):
        s_intact = self._create_sample_session("hash1", "hash1")
        assert s_intact.source_intact is True

        s_tampered = self._create_sample_session("hash1", "hash2")
        assert s_tampered.source_intact is False

        s_missing = self._create_sample_session("hash1", None)
        assert s_missing.source_intact is False

    def test_report_json_scrubbing(self):
        session = self._create_sample_session()
        session.errors.append("Exposed: api_key='FAKE_TEST_API_KEY_9999999999'")
        report = SandboxReport(session=session)
        json_out = report.to_json()
        assert "FAKE_TEST_API_KEY_9999999999" not in json_out
        data = json.loads(json_out)
        assert data["session"]["id"] == "test_session_123"

    def test_report_format_cli(self):
        session = self._create_sample_session()
        report = SandboxReport(session=session)
        cli_out = report.format_cli()
        assert "Sandbox Verification Report" in cli_out
        assert "test_session_123" in cli_out
        assert "MutableDefaultStrategy" in cli_out
        assert "APPLIED" in cli_out
        assert "Regression Verdict:    PASS" in cli_out
        assert "Original Repository:   UNCHANGED (Verified SHA-256 match)" in cli_out
