"""Abstract base class for all code smell, security, and pattern analysis rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
from typing import Optional

from analysis.findings.context import AnalysisContext
from analysis.findings.models import Confidence, Finding, FindingCategory, Severity


class BaseRule(ABC):
    """Abstract base class defining the contract for an analysis rule."""

    rule_id: str
    category: FindingCategory
    title: str
    default_severity: Severity
    default_confidence: Confidence
    description: str
    rationale: str
    recommendation: str

    @abstractmethod
    def check(self, context: AnalysisContext) -> list[Finding]:
        """Execute rule analysis against repository context and return findings."""
        pass

    def create_finding(
        self,
        file: str,
        start_line: int,
        end_line: int,
        evidence: Optional[str] = None,
        entity: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        rationale: Optional[str] = None,
        recommendation: Optional[str] = None,
        severity: Optional[Severity] = None,
        confidence: Optional[Confidence] = None,
    ) -> Finding:
        """Helper to create a validated, deterministically IDed Finding."""
        norm_file = file.replace("\\", "/")
        seed = f"{self.rule_id}:{norm_file}:{start_line}:{end_line}:{entity or ''}"
        fid = f"{self.rule_id}_{hashlib.md5(seed.encode('utf-8')).hexdigest()[:8]}"

        return Finding(
            id=fid,
            category=self.category,
            type=self.rule_id,
            severity=severity or self.default_severity,
            confidence=confidence or self.default_confidence,
            title=title or self.title,
            description=description or self.description,
            rationale=rationale or self.rationale,
            file=norm_file,
            start_line=start_line,
            end_line=end_line,
            entity=entity,
            evidence=evidence,
            recommendation=recommendation or self.recommendation,
            analyzer_name=self.__class__.__name__,
        )
