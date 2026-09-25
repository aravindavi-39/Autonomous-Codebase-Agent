"""Structured models for sandbox sessions, status tracking, patch results, and test comparisons."""

from __future__ import annotations

from enum import Enum
import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

# Secret masking patterns to ensure no raw credentials leak into reports
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token|bearer)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"FAKE_TEST_[A-Za-z0-9_]{10,}", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Scrub raw secrets and API keys from text."""
    if not text:
        return text
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(r"\1: [REDACTED_SECRET]" if r"\1" in pattern.pattern else "[REDACTED_SECRET]", redacted)
    return redacted


class SandboxStatus(str, Enum):
    """Lifecycle state of an isolated sandbox session."""

    CREATED = "CREATED"
    PATCHED = "PATCHED"
    TESTING = "TESTING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    CLEANED = "CLEANED"
    ERROR = "ERROR"


class ApprovalStatus(str, Enum):
    """Human approval state for sandbox application."""

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED_TO_SANDBOX = "APPLIED_TO_SANDBOX"
    VERIFIED = "VERIFIED"


class RegressionStatus(str, Enum):
    """Result of comparing baseline vs post-patch test runs."""

    PASS = "PASS"
    FAIL = "FAIL"
    BASELINE_FAILURE = "BASELINE_FAILURE"
    TEST_TIMEOUT = "TEST_TIMEOUT"
    TEST_ERROR = "TEST_ERROR"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    NO_TESTS = "NO_TESTS"
    SKIPPED = "SKIPPED"


class PatchApplicationResult(BaseModel):
    """Result of applying a proposed patch inside the sandbox."""

    success: bool = Field(..., description="Whether the patch applied successfully")
    finding_id: str = Field(..., description="Finding identifier")
    strategy: str = Field(..., description="Refactoring strategy applied")
    applied_files: list[str] = Field(default_factory=list, description="Repository-relative files modified")
    diff_applied: str = Field("", description="Unified diff text that was applied")
    errors: list[str] = Field(default_factory=list, description="Errors encountered during patching")
    warnings: list[str] = Field(default_factory=list, description="Warnings encountered during patching")


class TestRun(BaseModel):
    """Outcome of running test suite in the sandbox."""

    __test__ = False
    framework: str = Field("pytest", description="Test framework used (e.g. pytest)")
    command: list[str] = Field(default_factory=list, description="Command executed")
    status: str = Field("PASSED", description="Run status (PASSED, FAILED, TIMEOUT, ERROR, NO_TESTS)")
    return_code: int = Field(0, description="Process return code")
    total_tests: int = Field(0, description="Total tests discovered and executed")
    passed: int = Field(0, description="Number of passed tests")
    failed: int = Field(0, description="Number of failed tests")
    skipped: int = Field(0, description="Number of skipped tests")
    duration_seconds: float = Field(0.0, description="Duration in seconds")
    stdout: str = Field("", description="Captured stdout")
    stderr: str = Field("", description="Captured stderr")
    summary: str = Field("", description="Short human-readable summary")


class TestComparison(BaseModel):
    """Comparison of baseline vs post-patch test results."""

    __test__ = False
    baseline_run: Optional[TestRun] = Field(None, description="Test run prior to patch application")
    patched_run: Optional[TestRun] = Field(None, description="Test run following patch application")
    regression_status: RegressionStatus = Field(RegressionStatus.PASS, description="Overall regression verdict")
    summary: str = Field("", description="Summary description of test comparison")
    new_failures: list[str] = Field(default_factory=list, description="Tests that passed in baseline but failed in patch")
    fixed_failures: list[str] = Field(default_factory=list, description="Tests that failed in baseline but passed in patch")


class SandboxSession(BaseModel):
    """Metadata, status, and results for a single isolated sandbox execution."""

    id: str = Field(..., description="Unique session ID")
    source_repository: str = Field(..., description="Path or name of source repository")
    source_fingerprint_before: str = Field(..., description="SHA-256 fingerprint of source repo before session")
    source_fingerprint_after: Optional[str] = Field(None, description="SHA-256 fingerprint of source repo after session")
    sandbox_path: str = Field(..., description="Filesystem path of the isolated sandbox copy")
    status: SandboxStatus = Field(SandboxStatus.CREATED, description="Current sandbox status")
    approval_status: ApprovalStatus = Field(ApprovalStatus.PROPOSED, description="Human approval status")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    finding_id: Optional[str] = Field(None, description="Finding ID targeted for patch")
    proposal_id: Optional[str] = Field(None, description="Proposal ID")
    strategy_name: Optional[str] = Field(None, description="Refactoring strategy name")
    safety_classification: Optional[str] = Field(None, description="Safety classification of proposal")
    patch_result: Optional[PatchApplicationResult] = Field(None, description="Patch application outcome")
    test_comparison: Optional[TestComparison] = Field(None, description="Test regression comparison")
    verification_report: Optional[dict[str, Any]] = Field(None, description="Optional verification audit result")
    cleaned_up: bool = Field(False, description="Whether sandbox directory has been deleted")
    errors: list[str] = Field(default_factory=list, description="Top-level session errors")
    warnings: list[str] = Field(default_factory=list, description="Top-level session warnings")

    @property
    def source_intact(self) -> bool:
        """Returns True if the source repository fingerprint is verified unchanged."""
        if not self.source_fingerprint_after:
            return False
        return self.source_fingerprint_before == self.source_fingerprint_after


class SandboxReport(BaseModel):
    """Encapsulates session outcome for display and JSON serialization."""

    session: SandboxSession = Field(..., description="Completed sandbox session")

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to JSON, scrubbing any sensitive credentials."""
        raw_dict = self.model_dump(mode="json")
        json_str = json.dumps(raw_dict, indent=indent)
        return redact_secrets(json_str)

    def format_cli(self) -> str:
        """Format human-readable CLI report."""
        s = self.session
        lines: list[str] = [
            "Sandbox Verification Report",
            "===========================",
            "",
            f"Repository:            {s.source_repository}",
            f"Session ID:            {s.id}",
            f"Approval Status:       {s.approval_status.value}",
            f"Finding:               {s.finding_id or 'None'}",
            f"Strategy:              {s.strategy_name or 'None'}",
            f"Safety Tier:           {s.safety_classification or 'None'}",
            f"Patch Status:          {'APPLIED' if (s.patch_result and s.patch_result.success) else 'NOT_APPLIED'}",
        ]

        if s.patch_result and s.patch_result.applied_files:
            lines.append(f"Modified Files:        {', '.join(s.patch_result.applied_files)}")

        if s.test_comparison:
            tc = s.test_comparison
            base_str = tc.baseline_run.summary if tc.baseline_run else "None"
            patch_str = tc.patched_run.summary if tc.patched_run else "None"
            lines.extend([
                f"Baseline Tests:        {base_str}",
                f"Post-Patch Tests:      {patch_str}",
                f"Regression Verdict:    {tc.regression_status.value}",
            ])
        else:
            lines.append("Regression Verdict:    SKIPPED (no test comparison)")

        immutability = "UNCHANGED (Verified SHA-256 match)" if s.source_intact else "VERIFICATION_PENDING"
        lines.extend([
            f"Original Repository:   {immutability}",
            f"Sandbox Lifecycle:     {'CLEANED' if s.cleaned_up else f'RETAINED ({s.sandbox_path})'}",
            "",
        ])

        if s.errors:
            lines.append("Errors Encountered:")
            for err in s.errors:
                lines.append(f"  ✗ {err}")
            lines.append("")

        if s.warnings:
            lines.append("Warnings:")
            for warn in s.warnings:
                lines.append(f"  ⚠ {warn}")
            lines.append("")

        return "\n".join(lines)
