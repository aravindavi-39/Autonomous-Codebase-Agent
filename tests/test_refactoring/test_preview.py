"""Tests for preview formatting: plan table, diff output, validation display."""

import pytest

from refactoring.models import (
    DiffResult,
    RefactoringAction,
    RefactoringPlan,
    SafetyClassification,
    ValidationResult,
    ChangeProposal,
)
from refactoring.preview import (
    format_diff_output,
    format_plan_table,
    format_validation_result,
)
from analysis.findings.models import (
    Confidence,
    Finding,
    FindingCategory,
    Severity,
)


def _make_finding(**overrides):
    defaults = dict(
        id="PAT-003_abcd",
        category=FindingCategory.PATTERN,
        type="PAT-003",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        title="Test Finding",
        description="Test.",
        rationale="Test.",
        file="src/test.py",
        start_line=10,
        end_line=10,
        recommendation="Fix it.",
    )
    defaults.update(overrides)
    return Finding(**defaults)


def _make_plan():
    finding = _make_finding()
    proposal = ChangeProposal(
        finding_id=finding.id,
        finding_type=finding.type,
        strategy="TestStrategy",
        safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
        description="Test proposal description",
        rationale="Test rationale",
        source_file=finding.file,
        source_start_line=finding.start_line,
        source_end_line=finding.end_line,
    )
    action = RefactoringAction(
        finding=finding,
        proposal=proposal,
        priority=3,
    )
    return RefactoringPlan(
        repository="test-repo",
        actions=[action],
        summary={"total_actions": 1, "safe_automatic": 1, "review_required": 0, "unsupported": 0},
    )


class TestFormatPlanTable:
    def test_plan_table_output(self):
        plan = _make_plan()
        text = format_plan_table(plan)
        assert "test-repo" in text
        assert "PAT-003_abcd" in text
        assert "TestStrategy" in text
        assert "Total:" in text

    def test_empty_plan(self):
        plan = RefactoringPlan(
            repository="empty-repo",
            actions=[],
            summary={"total_actions": 0, "safe_automatic": 0, "review_required": 0, "unsupported": 0},
        )
        text = format_plan_table(plan)
        assert "empty-repo" in text
        assert "Total: 0" in text


class TestFormatDiffOutput:
    def test_diff_output_contains_diff_text(self):
        diff = DiffResult(
            file_path="src/test.py",
            unified_diff="--- a/src/test.py\n+++ b/src/test.py\n@@ -1 +1 @@\n-old\n+new\n",
        )
        text = format_diff_output([diff])
        assert "---" in text
        assert "+++" in text
        assert "-old" in text
        assert "+new" in text


class TestFormatValidationResult:
    def test_valid_result_output(self):
        result = ValidationResult(valid=True, errors=[], warnings=[], proposal_id="test")
        text = format_validation_result(result)
        assert "PASSED" in text

    def test_invalid_result_output(self):
        result = ValidationResult(
            valid=False,
            errors=["Syntax error in test.py"],
            warnings=["Minor issue"],
            proposal_id="test",
        )
        text = format_validation_result(result)
        assert "FAILED" in text
        assert "Syntax error" in text
