"""Tests for refactoring models: construction, serialization, enum values, safety classifications."""

import json
import pytest

from refactoring.models import (
    ChangeProposal,
    DiffResult,
    FileChange,
    RefactoringAction,
    RefactoringPlan,
    SafetyClassification,
    TextEdit,
    ValidationResult,
)
from analysis.findings.models import (
    Confidence,
    Finding,
    FindingCategory,
    Severity,
)


def _make_finding(**overrides):
    defaults = dict(
        id="PAT-003_abcd1234",
        category=FindingCategory.PATTERN,
        type="PAT-003",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        title="Mutable default argument",
        description="Function has a mutable default.",
        rationale="Mutable defaults are shared across calls.",
        file="src/patterns.py",
        start_line=14,
        end_line=14,
        recommendation="Use None as default.",
    )
    defaults.update(overrides)
    return Finding(**defaults)


# ───── SafetyClassification ─────


class TestSafetyClassification:
    def test_enum_values(self):
        assert SafetyClassification.SAFE_AUTOMATIC_PROPOSAL.value == "SAFE_AUTOMATIC_PROPOSAL"
        assert SafetyClassification.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"
        assert SafetyClassification.UNSUPPORTED.value == "UNSUPPORTED"

    def test_description_property(self):
        assert "safely" in SafetyClassification.SAFE_AUTOMATIC_PROPOSAL.description.lower()
        assert "review" in SafetyClassification.REVIEW_REQUIRED.description.lower()
        assert "manual" in SafetyClassification.UNSUPPORTED.description.lower()


# ───── TextEdit ─────


class TestTextEdit:
    def test_construction(self):
        edit = TextEdit(
            start_line=10,
            end_line=12,
            original_text="old code",
            replacement_text="new code",
        )
        assert edit.start_line == 10
        assert edit.end_line == 12
        assert edit.original_text == "old code"
        assert edit.replacement_text == "new code"


# ───── FileChange ─────


class TestFileChange:
    def test_construction_with_edits(self):
        edit = TextEdit(start_line=1, end_line=1, original_text="a", replacement_text="b")
        fc = FileChange(file_path="src/foo.py", edits=[edit])
        assert fc.file_path == "src/foo.py"
        assert len(fc.edits) == 1


# ───── ChangeProposal ─────


class TestChangeProposal:
    def test_construction(self):
        proposal = ChangeProposal(
            finding_id="PAT-003_abcd",
            finding_type="PAT-003",
            strategy="MutableDefaultStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            file_changes=[],
            description="Fix mutable default",
            rationale="Prevents leaked state",
            source_file="src/foo.py",
            source_start_line=10,
            source_end_line=10,
        )
        assert proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
        assert proposal.strategy == "MutableDefaultStrategy"

    def test_serialization_roundtrip(self):
        proposal = ChangeProposal(
            finding_id="PAT-003_abcd",
            finding_type="PAT-003",
            strategy="MutableDefaultStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            file_changes=[FileChange(file_path="x.py", edits=[])],
            description="Fix",
            rationale="Reason",
            source_file="x.py",
            source_start_line=1,
            source_end_line=1,
        )
        data = proposal.model_dump(mode="json")
        restored = ChangeProposal(**data)
        assert restored.finding_id == proposal.finding_id
        assert restored.safety == proposal.safety


# ───── RefactoringPlan ─────


class TestRefactoringPlan:
    def _make_plan(self):
        finding = _make_finding()
        proposal = ChangeProposal(
            finding_id=finding.id,
            finding_type=finding.type,
            strategy="TestStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            description="Test",
            rationale="Test",
            source_file=finding.file,
            source_start_line=finding.start_line,
            source_end_line=finding.end_line,
        )
        action = RefactoringAction(
            finding=finding,
            proposal=proposal,
            priority=3,
            risk_notes="",
        )
        review_proposal = ChangeProposal(
            finding_id="PAT-001_efgh",
            finding_type="PAT-001",
            strategy="BroadExceptionStrategy",
            safety=SafetyClassification.REVIEW_REQUIRED,
            description="Review broad except",
            rationale="Context dependent",
            source_file="src/foo.py",
            source_start_line=5,
            source_end_line=8,
        )
        review_finding = _make_finding(
            id="PAT-001_efgh",
            type="PAT-001",
            category=FindingCategory.PATTERN,
            start_line=5,
            end_line=8,
        )
        review_action = RefactoringAction(
            finding=review_finding,
            proposal=review_proposal,
            priority=4,
            risk_notes="Human review required.",
        )
        return RefactoringPlan(
            repository="test-repo",
            actions=[action, review_action],
            summary={"total_actions": 2, "safe_automatic": 1, "review_required": 1, "unsupported": 0},
        )

    def test_filter_safe_only(self):
        plan = self._make_plan()
        safe = plan.filter_safe_only()
        assert len(safe) == 1
        assert safe[0].proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL

    def test_filter_by_finding(self):
        plan = self._make_plan()
        matched = plan.filter_by_finding("PAT-003_abcd1234")
        assert len(matched) == 1

    def test_to_json(self):
        plan = self._make_plan()
        json_str = plan.to_json()
        data = json.loads(json_str)
        assert data["repository"] == "test-repo"
        assert len(data["actions"]) == 2


# ───── ValidationResult ─────


class TestValidationResult:
    def test_valid_result(self):
        result = ValidationResult(valid=True, errors=[], warnings=[], proposal_id="test")
        assert result.valid is True

    def test_invalid_result(self):
        result = ValidationResult(
            valid=False,
            errors=["Syntax error"],
            warnings=["Minor issue"],
            proposal_id="test",
        )
        assert result.valid is False
        assert len(result.errors) == 1
