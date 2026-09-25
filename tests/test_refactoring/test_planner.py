"""Tests for RefactoringPlanner: plan generation, filtering, priority ordering."""

from pathlib import Path

import pytest

from analysis.analyzer import RepositoryAnalyzer
from analysis.findings.context import AnalysisContext
from analysis.findings.engine import AnalysisEngine
from analysis.findings.models import AnalysisReport, FindingCategory, Severity
from analysis.graph_builder import CodeGraphBuilder
from ingestion.pipeline import IngestionPipeline
from refactoring.models import RefactoringPlan, SafetyClassification
from refactoring.planner import RefactoringPlanner

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"


@pytest.fixture(scope="module")
def full_context():
    """Build full analysis pipeline from vulnerable_repo."""
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(FIXTURE_DIR))
    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(FIXTURE_DIR), manifest=manifest)
    builder = CodeGraphBuilder()
    code_graph = builder.build_graph(code_index)
    context = AnalysisContext(
        manifest=manifest,
        code_index=code_index,
        code_graph=code_graph,
    )
    engine = AnalysisEngine()
    report = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=code_graph,
    )
    return context, report


class TestRefactoringPlanner:
    def test_plan_generates_actions(self, full_context):
        context, report = full_context
        planner = RefactoringPlanner()
        plan = planner.plan(report=report, context=context)

        assert isinstance(plan, RefactoringPlan)
        assert plan.repository == report.repository
        assert len(plan.actions) > 0
        assert plan.summary["total_actions"] == len(plan.actions)

    def test_plan_safe_only_filter(self, full_context):
        context, report = full_context
        planner = RefactoringPlanner()
        plan = planner.plan(report=report, context=context, safe_only=True)

        for action in plan.actions:
            assert action.proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL

    def test_plan_finding_id_filter(self, full_context):
        context, report = full_context
        # Get any finding from the report
        if not report.findings:
            pytest.skip("No findings to filter")
        target_finding = report.findings[0]

        planner = RefactoringPlanner()
        plan = planner.plan(report=report, context=context, finding_id=target_finding.id)

        # Every action should reference the target finding
        for action in plan.actions:
            assert action.finding.id == target_finding.id

    def test_plan_priority_ordering(self, full_context):
        """Actions should be sorted by priority (severity: CRITICAL first)."""
        context, report = full_context
        planner = RefactoringPlanner()
        plan = planner.plan(report=report, context=context)

        # Check priorities are non-decreasing
        for i in range(len(plan.actions) - 1):
            assert plan.actions[i].priority <= plan.actions[i + 1].priority or \
                   (plan.actions[i].priority == plan.actions[i + 1].priority)

    def test_plan_empty_report(self, full_context):
        """Empty report should produce empty plan."""
        context, _ = full_context
        empty_report = AnalysisReport(repository="empty", findings=[], summary={})
        planner = RefactoringPlanner()
        plan = planner.plan(report=empty_report, context=context)
        assert len(plan.actions) == 0
        assert plan.summary["total_actions"] == 0

    def test_plan_nonexistent_finding_id(self, full_context):
        """Filtering by non-existent finding ID produces empty plan."""
        context, report = full_context
        planner = RefactoringPlanner()
        plan = planner.plan(report=report, context=context, finding_id="NONEXISTENT_99999")
        assert len(plan.actions) == 0
