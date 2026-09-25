"""Structured models for codebase findings, security issues, code smells, and reports."""

from __future__ import annotations

from enum import Enum
import json
from typing import Any, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for detected codebase findings."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def level(self) -> int:
        levels = {
            "INFO": 0,
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
        }
        return levels[self.value]

    @classmethod
    def from_str(cls, val: str) -> Severity:
        val_upper = val.strip().upper()
        for member in cls:
            if member.value == val_upper:
                return member
        raise ValueError(f"Unknown severity level: {val}")


class Confidence(str, Enum):
    """Confidence levels for static detection accuracy."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def level(self) -> int:
        levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        return levels[self.value]

    @classmethod
    def from_str(cls, val: str) -> Confidence:
        val_upper = val.strip().upper()
        for member in cls:
            if member.value == val_upper:
                return member
        raise ValueError(f"Unknown confidence level: {val}")


class FindingCategory(str, Enum):
    """Broad classification of findings."""

    CODE_SMELL = "CODE_SMELL"
    SECURITY = "SECURITY"
    PATTERN = "PATTERN"

    @classmethod
    def from_str(cls, val: str) -> FindingCategory:
        norm = val.strip().upper().replace(" ", "_").replace("-", "_")
        for member in cls:
            if member.value == norm or member.name == norm:
                return member
        if "SMELL" in norm:
            return cls.CODE_SMELL
        if "SEC" in norm:
            return cls.SECURITY
        if "PAT" in norm:
            return cls.PATTERN
        raise ValueError(f"Unknown category: {val}")


class Finding(BaseModel):
    """A single normalized finding with exact source location, rationale, and recommendation."""

    id: str = Field(..., description="Unique deterministic finding identifier")
    category: FindingCategory = Field(..., description="Finding category")
    type: str = Field(..., description="Specific finding rule identifier, e.g. 'LONG_FUNCTION'")
    severity: Severity = Field(..., description="Severity level")
    confidence: Confidence = Field(..., description="Detection confidence")
    title: str = Field(..., description="Brief human-readable title")
    description: str = Field(..., description="Clear explanation of the detected problem")
    rationale: str = Field(..., description="Why this issue matters for software quality / security")
    file: str = Field(..., description="Repository-relative file path")
    start_line: int = Field(..., description="Starting source line (1-indexed)")
    end_line: int = Field(..., description="Ending source line (inclusive)")
    entity: Optional[str] = Field(None, description="Name of the affected symbol (class/function/module)")
    evidence: Optional[str] = Field(None, description="Code snippet or syntactic evidence")
    recommendation: str = Field(..., description="Actionable recommendation to resolve the issue")
    analyzer_name: str = Field("codebase-analyzer", description="Analyzer or rule engine name")

    def to_citation_str(self) -> str:
        """Format citation as '📄 file:start-end (entity)'."""
        entity_suffix = f" ({self.entity})" if self.entity else ""
        if self.start_line == self.end_line:
            return f"📄 {self.file}:{self.start_line}{entity_suffix}"
        return f"📄 {self.file}:{self.start_line}-{self.end_line}{entity_suffix}"


class AnalysisReport(BaseModel):
    """Comprehensive analysis report containing summary statistics and findings."""

    repository: str = Field(..., description="Name or path of the analyzed repository")
    files_analyzed: int = Field(0, description="Total source files analyzed")
    total_findings: int = Field(0, description="Total findings detected")
    findings: list[Finding] = Field(default_factory=list, description="List of detected findings")
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary counts and metrics")

    def filter_findings(
        self,
        min_severity: Optional[Severity] = None,
        category: Optional[FindingCategory] = None,
    ) -> list[Finding]:
        """Filter findings by minimum severity and/or category."""
        res = self.findings
        if min_severity is not None:
            res = [f for f in res if f.severity.level >= min_severity.level]
        if category is not None:
            res = [f for f in res if f.category == category]
        return res

    def to_json(self, indent: int = 2) -> str:
        """Serialize complete report to formatted JSON string."""
        return json.dumps(self.model_dump(mode="json"), indent=indent)

    def format_cli(
        self,
        min_severity: Optional[Severity] = None,
        category: Optional[FindingCategory] = None,
    ) -> str:
        """Format report into human-readable terminal output."""
        filtered = self.filter_findings(min_severity=min_severity, category=category)

        lines: list[str] = [
            "Codebase Analysis Report",
            "========================",
            "",
            "Summary",
            "-------",
            f"Files analyzed: {self.files_analyzed}",
            f"Findings: {len(filtered)}",
            f"Critical: {self.summary.get('critical', 0)}",
            f"High: {self.summary.get('high', 0)}",
            f"Medium: {self.summary.get('medium', 0)}",
            f"Low: {self.summary.get('low', 0)}",
            f"Info: {self.summary.get('info', 0)}",
            "",
        ]

        # Group findings by category
        security_findings = [f for f in filtered if f.category == FindingCategory.SECURITY]
        smell_findings = [f for f in filtered if f.category == FindingCategory.CODE_SMELL]
        pattern_findings = [f for f in filtered if f.category == FindingCategory.PATTERN]

        if security_findings:
            lines.extend(["Security Findings", "-----------------"])
            for f in security_findings:
                lines.append(f"[{f.severity.value}] {f.title}")
                lines.append(f"File: {f.file}:{f.start_line}-{f.end_line}")
                lines.append(f"Confidence: {f.confidence.value}")
                if f.evidence:
                    lines.append(f"Evidence:\n{f.evidence.strip()}")
                lines.append(f"Why:\n{f.rationale}")
                lines.append(f"Recommendation:\n{f.recommendation}")
                lines.append("")

        if smell_findings:
            lines.extend(["Code Smells", "-----------"])
            for f in smell_findings:
                lines.append(f"[{f.severity.value}] {f.title}")
                lines.append(f"File: {f.file}:{f.start_line}-{f.end_line}")
                if f.entity:
                    lines.append(f"Entity: {f.entity}")
                lines.append(f"Confidence: {f.confidence.value}")
                if f.evidence:
                    lines.append(f"Evidence:\n{f.evidence.strip()}")
                lines.append(f"Why:\n{f.rationale}")
                lines.append(f"Recommendation:\n{f.recommendation}")
                lines.append("")

        if pattern_findings:
            lines.extend(["Coding Patterns", "---------------"])
            for f in pattern_findings:
                lines.append(f"[{f.severity.value}] {f.title}")
                lines.append(f"File: {f.file}:{f.start_line}-{f.end_line}")
                lines.append(f"Confidence: {f.confidence.value}")
                if f.evidence:
                    lines.append(f"Evidence:\n{f.evidence.strip()}")
                lines.append(f"Why:\n{f.rationale}")
                lines.append(f"Recommendation:\n{f.recommendation}")
                lines.append("")

        if not filtered:
            lines.append("No findings detected matching criteria.")
            lines.append("")

        return "\n".join(lines)
