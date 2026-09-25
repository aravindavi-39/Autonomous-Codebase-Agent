"""Structured models for refactoring plans, change proposals, diffs, and validation results."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from analysis.findings.models import Finding, Severity


class SafetyClassification(str, Enum):
    """Safety tier for a proposed refactoring transformation."""

    SAFE_AUTOMATIC_PROPOSAL = "SAFE_AUTOMATIC_PROPOSAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"

    @property
    def description(self) -> str:
        descriptions = {
            "SAFE_AUTOMATIC_PROPOSAL": "Deterministic, semantics-preserving transformation that can be safely proposed.",
            "REVIEW_REQUIRED": "Transformation requires human review before application.",
            "UNSUPPORTED": "Automated refactoring is not supported; manual intervention required.",
        }
        return descriptions[self.value]


class TextEdit(BaseModel):
    """A single text replacement within a file."""

    start_line: int = Field(..., description="Start line (1-indexed, inclusive)")
    end_line: int = Field(..., description="End line (1-indexed, inclusive)")
    original_text: str = Field(..., description="Original text being replaced")
    replacement_text: str = Field(..., description="New text to insert")


class FileChange(BaseModel):
    """Aggregated edits for a single file."""

    file_path: str = Field(..., description="Repository-relative file path")
    edits: list[TextEdit] = Field(default_factory=list, description="Ordered list of text edits")


class ChangeProposal(BaseModel):
    """A proposed fix for a single finding."""

    finding_id: str = Field(..., description="ID of the finding this proposal addresses")
    finding_type: str = Field(..., description="Type/rule ID of the finding (e.g. PAT-003)")
    strategy: str = Field(..., description="Name of the refactoring strategy applied")
    safety: SafetyClassification = Field(..., description="Safety classification")
    file_changes: list[FileChange] = Field(default_factory=list, description="Proposed file changes")
    description: str = Field(..., description="Human-readable description of the proposed change")
    rationale: str = Field(..., description="Why this transformation is safe/needed")
    source_file: str = Field(..., description="File where the finding was detected")
    source_start_line: int = Field(..., description="Start line of the finding")
    source_end_line: int = Field(..., description="End line of the finding")


class RefactoringAction(BaseModel):
    """A prioritized item in the refactoring plan."""

    finding: Finding = Field(..., description="The original analysis finding")
    proposal: ChangeProposal = Field(..., description="The proposed change")
    priority: int = Field(..., description="Priority rank (lower = higher priority)")
    risk_notes: str = Field("", description="Any risk or caveats for this action")


class RefactoringPlan(BaseModel):
    """Top-level refactoring plan containing all proposed actions."""

    repository: str = Field(..., description="Repository name or path")
    actions: list[RefactoringAction] = Field(default_factory=list, description="Ordered refactoring actions")
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary statistics")

    def filter_safe_only(self) -> list[RefactoringAction]:
        """Return only SAFE_AUTOMATIC_PROPOSAL actions."""
        return [a for a in self.actions if a.proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL]

    def filter_by_finding(self, finding_id: str) -> list[RefactoringAction]:
        """Return actions matching a specific finding ID."""
        return [a for a in self.actions if a.finding.id == finding_id]

    def to_json(self, indent: int = 2) -> str:
        """Serialize complete plan to formatted JSON string."""
        return json.dumps(self.model_dump(mode="json"), indent=indent)


class DiffResult(BaseModel):
    """Result of unified diff generation for a single file."""

    file_path: str = Field(..., description="Repository-relative file path")
    unified_diff: str = Field(..., description="Unified diff text")
    original_content: str = Field("", description="Original file content")
    modified_content: str = Field("", description="Modified file content after edits")


class ValidationResult(BaseModel):
    """Outcome of diff validation."""

    valid: bool = Field(..., description="Whether the diff passed all validation checks")
    errors: list[str] = Field(default_factory=list, description="Validation errors (fatal)")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings (non-fatal)")
    proposal_id: str = Field("", description="ID of the validated proposal/finding")
