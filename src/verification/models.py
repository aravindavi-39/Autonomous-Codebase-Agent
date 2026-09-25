"""Structured models for the Verification Engine, lint results, finding deltas, and policy reports."""

from __future__ import annotations

from enum import Enum
import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from analysis.findings.models import Finding
from sandbox.models import (
    RegressionStatus,
    TestComparison,
    TestRun,
    redact_secrets,
)


class LintSeverity(str, Enum):
    """Severity of a lint violation."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class LintViolation(BaseModel):
    """A single detected lint or syntax violation."""

    file: str = Field(..., description="Repository-relative file path")
    line: int = Field(..., description="1-indexed line number")
    column: int = Field(1, description="1-indexed column number")
    code: str = Field(..., description="Rule code (e.g. E999, W291, AST_SYNTAX)")
    message: str = Field(..., description="Description of the violation")
    severity: LintSeverity = Field(LintSeverity.WARNING, description="Violation severity")


class LintRunResult(BaseModel):
    """Outcome of lint and syntax checks across a codebase."""

    status: str = Field("PASSED", description="Linter status (PASSED, WARNING, FAILED, SKIPPED, ERROR)")
    linter_name: str = Field("ast_linter", description="Name of the linter tool used")
    violations: list[LintViolation] = Field(default_factory=list, description="List of detected violations")
    files_checked: int = Field(0, description="Total files inspected")
    error_count: int = Field(0, description="Number of error-level violations")
    warning_count: int = Field(0, description="Number of warning-level violations")
    skipped: bool = Field(False, description="Whether linting was skipped (--no-lint)")
    summary: str = Field("", description="Short human-readable summary")


class FindingDelta(BaseModel):
    """Evidence-based comparison between baseline findings and post-patch findings."""

    target_finding_id: Optional[str] = Field(None, description="The finding ID targeted for refactoring")
    target_existed_in_baseline: bool = Field(False, description="Whether target finding was detected in baseline")
    target_resolved: bool = Field(False, description="Whether target finding was genuinely eliminated after patch")
    baseline_findings_count: int = Field(0, description="Total findings present in baseline analysis")
    post_patch_findings_count: int = Field(0, description="Total findings present in post-patch analysis")
    resolved_findings: list[Finding] = Field(
        default_factory=list,
        description="Findings present in baseline that are no longer detected after patch",
    )
    remaining_findings: list[Finding] = Field(
        default_factory=list,
        description="Pre-existing findings that were not modified and remain present",
    )
    new_findings: list[Finding] = Field(
        default_factory=list,
        description="Genuinely newly introduced findings that did not exist in baseline",
    )
    summary: str = Field("", description="Summary description of findings delta")


class VerificationVerdict(str, Enum):
    """Overall evaluation verdict of verification policy."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class PolicyMode(str, Enum):
    """Policy strictness tier."""

    STRICT = "STRICT"
    LENIENT = "LENIENT"


class VerificationPolicy(BaseModel):
    """Configurable evaluation policy for accepting or rejecting refactored code."""

    mode: PolicyMode = Field(PolicyMode.STRICT, description="Policy tier")
    require_target_resolution: bool = Field(
        True,
        description="If a target finding is specified, require evidence that it was eliminated",
    )
    require_zero_test_regressions: bool = Field(
        True,
        description="Require that no new unit test failures were introduced",
    )
    allow_new_findings: bool = Field(
        False,
        description="Whether to permit newly introduced code smells or security findings",
    )
    fail_on_lint_errors: bool = Field(
        True,
        description="Fail verification if syntax or fatal lint errors are detected",
    )
    fail_on_lint_warnings: bool = Field(
        False,
        description="Fail verification if non-fatal lint warnings are detected (True in STRICT)",
    )

    @classmethod
    def strict(cls) -> VerificationPolicy:
        """Create a strict verification policy."""
        return cls(
            mode=PolicyMode.STRICT,
            require_target_resolution=True,
            require_zero_test_regressions=True,
            allow_new_findings=False,
            fail_on_lint_errors=True,
            fail_on_lint_warnings=True,
        )

    @classmethod
    def lenient(cls) -> VerificationPolicy:
        """Create a lenient verification policy."""
        return cls(
            mode=PolicyMode.LENIENT,
            require_target_resolution=True,
            require_zero_test_regressions=True,
            allow_new_findings=False,
            fail_on_lint_errors=True,
            fail_on_lint_warnings=False,
        )


class VerificationReport(BaseModel):
    """Consolidated verification report across tests, linters, finding deltas, and policy gates."""

    repository: str = Field(..., description="Repository path or identifier")
    timestamp: str = Field(..., description="ISO 8601 execution timestamp")
    verdict: VerificationVerdict = Field(VerificationVerdict.PASSED, description="Final verification verdict")
    policy: VerificationPolicy = Field(default_factory=VerificationPolicy.strict, description="Applied policy")
    target_finding_id: Optional[str] = Field(None, description="Target finding ID if evaluating resolution")
    test_run: Optional[TestRun] = Field(None, description="Executed test run")
    test_comparison: Optional[TestComparison] = Field(None, description="Baseline vs post-patch test comparison")
    test_skipped: bool = Field(False, description="Whether tests were skipped (--no-tests)")
    lint_run: Optional[LintRunResult] = Field(None, description="Executed lint and syntax checks")
    lint_skipped: bool = Field(False, description="Whether linting was skipped (--no-lint)")
    finding_delta: Optional[FindingDelta] = Field(None, description="Analysis findings delta comparison")
    source_fingerprint_before: str = Field("", description="Source SHA-256 fingerprint before verification")
    source_fingerprint_after: str = Field("", description="Source SHA-256 fingerprint after verification")
    source_intact: bool = Field(True, description="Whether source repository remained 100% byte-for-byte unchanged")
    messages: list[str] = Field(default_factory=list, description="Verification verdict summary messages")
    errors: list[str] = Field(default_factory=list, description="Verification failure explanations")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warning notices")

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON, scrubbing raw secret tokens."""
        raw_dict = self.model_dump(mode="json")
        return redact_secrets(json.dumps(raw_dict, indent=indent))

    def format_cli(self) -> str:
        """Format human-readable CLI report."""
        lines = [
            "Verification & Audit Report",
            "===========================",
            "",
            f"Repository:            {self.repository}",
            f"Policy Mode:           {self.policy.mode.value}",
            f"Final Verdict:         {self.verdict.value}",
        ]

        if self.target_finding_id:
            lines.append(f"Target Finding:        {self.target_finding_id}")
            if self.finding_delta:
                res_str = "YES (Confirmed eliminated)" if self.finding_delta.target_resolved else "NO (Still present)"
                lines.append(f"Target Resolved:       {res_str}")

        if self.finding_delta:
            fd = self.finding_delta
            lines.append(
                f"Findings Delta:        {len(fd.resolved_findings)} resolved, "
                f"{len(fd.remaining_findings)} unchanged, {len(fd.new_findings)} new"
            )

        # Test Status
        if self.test_skipped:
            lines.append("Test Suite:            SKIPPED (--no-tests)")
        elif self.test_comparison:
            tc = self.test_comparison
            base_s = tc.baseline_run.summary if tc.baseline_run else "None"
            patch_s = tc.patched_run.summary if tc.patched_run else "None"
            lines.append(f"Baseline Tests:        {base_s}")
            lines.append(f"Post-Patch Tests:      {patch_s}")
            lines.append(f"Test Regression:       {tc.regression_status.value}")
        elif self.test_run:
            lines.append(f"Test Suite:            {self.test_run.status} ({self.test_run.summary})")

        # Lint Status
        if self.lint_skipped:
            lines.append("Lint & Syntax:         SKIPPED (--no-lint)")
        elif self.lint_run:
            lines.append(f"Lint & Syntax:         {self.lint_run.status} ({self.lint_run.summary})")

        # Repository Immutability
        imm_str = "UNCHANGED (Verified SHA-256 match)" if self.source_intact else "MODIFIED_ERROR"
        lines.extend([
            f"Original Repository:   {imm_str}",
            "",
        ])

        if self.messages:
            lines.append("Summary Observations:")
            for msg in self.messages:
                lines.append(f"  • {msg}")
            lines.append("")

        if self.errors:
            lines.append("Failures & Violations:")
            for err in self.errors:
                lines.append(f"  ✗ {err}")
            lines.append("")

        if self.warnings:
            lines.append("Warnings:")
            for warn in self.warnings:
                lines.append(f"  ⚠ {warn}")
            lines.append("")

        return "\n".join(lines)
