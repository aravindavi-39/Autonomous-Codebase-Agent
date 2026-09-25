"""RefactoringPlanner: produces a prioritized RefactoringPlan from analysis findings."""

from __future__ import annotations

from typing import Optional

from analysis.findings.context import AnalysisContext
from analysis.findings.models import AnalysisReport, Finding, Severity
from refactoring.models import (
    RefactoringAction,
    RefactoringPlan,
    SafetyClassification,
)
from refactoring.strategies import StrategyRegistry, get_default_strategy_registry
from utils.logger import setup_logger

logger = setup_logger(__name__)


# Priority mapping: CRITICAL=1 (highest), INFO=5 (lowest)
_SEVERITY_PRIORITY = {
    Severity.CRITICAL: 1,
    Severity.HIGH: 2,
    Severity.MEDIUM: 3,
    Severity.LOW: 4,
    Severity.INFO: 5,
}


class RefactoringPlanner:
    """Generates refactoring plans from analysis reports using registered strategies."""

    def __init__(self, registry: Optional[StrategyRegistry] = None) -> None:
        self.registry = registry or get_default_strategy_registry()

    def plan(
        self,
        report: AnalysisReport,
        context: AnalysisContext,
        finding_id: Optional[str] = None,
        safe_only: bool = False,
    ) -> RefactoringPlan:
        """Generate a RefactoringPlan from an AnalysisReport.

        Args:
            report: The analysis report containing findings.
            context: The analysis context for reading source files.
            finding_id: If set, only plan for this specific finding.
            safe_only: If True, only include SAFE_AUTOMATIC_PROPOSAL actions.

        Returns:
            A RefactoringPlan with prioritized actions.
        """
        actions: list[RefactoringAction] = []

        findings = report.findings
        if finding_id:
            findings = [f for f in findings if f.id == finding_id]

        for finding in findings:
            strategy = self.registry.get_strategy(finding)
            if strategy is None:
                logger.debug("No strategy for finding type %s (id=%s)", finding.type, finding.id)
                continue

            try:
                proposal = strategy.propose(finding, context)
            except Exception as exc:
                logger.warning("Strategy %s failed for finding %s: %s", strategy.strategy_name, finding.id, exc)
                continue

            # Apply safe_only filter
            if safe_only and proposal.safety != SafetyClassification.SAFE_AUTOMATIC_PROPOSAL:
                continue

            priority = _SEVERITY_PRIORITY.get(finding.severity, 5)

            # Generate risk notes based on safety classification
            risk_notes = ""
            if proposal.safety == SafetyClassification.REVIEW_REQUIRED:
                risk_notes = "Human review required before applying this change."
            elif proposal.safety == SafetyClassification.UNSUPPORTED:
                risk_notes = "Automated refactoring is not supported. Manual intervention required."

            action = RefactoringAction(
                finding=finding,
                proposal=proposal,
                priority=priority,
                risk_notes=risk_notes,
            )
            actions.append(action)

        # Sort by priority (lower number = higher priority), then by file and line
        actions.sort(key=lambda a: (a.priority, a.finding.file, a.finding.start_line))

        # Build summary
        summary = {
            "total_actions": len(actions),
            "safe_automatic": sum(
                1 for a in actions if a.proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
            ),
            "review_required": sum(
                1 for a in actions if a.proposal.safety == SafetyClassification.REVIEW_REQUIRED
            ),
            "unsupported": sum(
                1 for a in actions if a.proposal.safety == SafetyClassification.UNSUPPORTED
            ),
        }

        logger.info(
            "Refactoring plan: %d actions (%d safe, %d review, %d unsupported)",
            summary["total_actions"],
            summary["safe_automatic"],
            summary["review_required"],
            summary["unsupported"],
        )

        return RefactoringPlan(
            repository=report.repository,
            actions=actions,
            summary=summary,
        )
