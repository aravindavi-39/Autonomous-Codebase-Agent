"""Comprehensive unit and rendering tests for all 11 Web UI pages."""

from __future__ import annotations

from pathlib import Path
import pytest

from analysis.analyzer import RepositoryAnalyzer
from analysis.findings.context import AnalysisContext
from analysis.findings.engine import AnalysisEngine
from analysis.graph_builder import CodeGraphBuilder
from ingestion.pipeline import IngestionPipeline
from refactoring.planner import RefactoringPlanner

import web.app as app
import web.pages.architecture as page_architecture
import web.pages.code_understanding as page_code_understanding
import web.pages.dashboard as page_dashboard
import web.pages.findings as page_findings
import web.pages.qa as page_qa
import web.pages.refactoring as page_refactoring
import web.pages.reports as page_reports
import web.pages.repository as page_repository
import web.pages.safety as page_safety
import web.pages.sandbox as page_sandbox
import web.pages.verification as page_verification
import web.state as state


ALL_PAGES = [
    page_dashboard,
    page_repository,
    page_code_understanding,
    page_architecture,
    page_qa,
    page_findings,
    page_refactoring,
    page_sandbox,
    page_verification,
    page_reports,
    page_safety,
]


def test_all_pages_have_render_function():
    """Verify that every page module exposes a callable render() function."""
    for page in ALL_PAGES:
        assert hasattr(page, "render"), f"{page.__name__} must expose a render function"
        assert callable(page.render), f"{page.__name__}.render must be callable"


def test_pages_routing_table_completeness():
    """Verify that web/app.py routing table contains all 11 expected pages."""
    expected_pages = [
        "📊 Dashboard",
        "📁 Repository & Ingestion",
        "🧠 Code Understanding",
        "🕸️ Architecture & Graph",
        "💬 Codebase Q&A",
        "🔍 Findings & Security",
        "🛠️ Refactoring & Diffs",
        "🧪 Sandbox Apply",
        "📋 Verification Engine",
        "📑 Reports & Exports",
        "🛡️ Safety & Settings",
    ]
    assert len(app.PAGES) == 11
    for page_name in expected_pages:
        assert page_name in app.PAGES, f"Missing page in routing table: {page_name}"
        assert callable(app.PAGES[page_name])


def test_empty_state_rendering_all_pages():
    """Verify that every page renders cleanly without exception when no repo is loaded."""
    state.reset_session_cache()
    assert not state.is_repo_loaded()

    for page in ALL_PAGES:
        try:
            page.render()
        except Exception as exc:
            pytest.fail(f"Empty-state rendering failed for {page.__name__}: {exc}")


@pytest.fixture
def populated_repo_session():
    """Load sandbox_test_repo through the full analysis pipeline into session state."""
    repo_path = Path("tests/fixtures/sandbox_test_repo").resolve()
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(repo_path))

    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(repo_path), manifest=manifest)

    builder = CodeGraphBuilder()
    code_graph = builder.build_graph(code_index)

    engine = AnalysisEngine()
    report = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=code_graph,
        root_path=repo_path,
    )

    context = AnalysisContext(
        manifest=manifest,
        code_index=code_index,
        code_graph=code_graph,
        root_path=repo_path,
    )

    planner = RefactoringPlanner()
    plan = planner.plan(report=report, context=context)

    state.reset_session_cache()
    state.set_repo_path(str(repo_path))
    state.set_initial_sha256("test-sha256-hash-value-1234567890")
    state.set_manifest(manifest)
    state.set_code_index(code_index)
    state.set_code_graph(code_graph)
    state.set_analysis_context(context)
    state.set_analysis_report(report)
    state.set_refactoring_plan(plan)

    yield {
        "manifest": manifest,
        "code_index": code_index,
        "code_graph": code_graph,
        "report": report,
        "plan": plan,
    }
    state.reset_session_cache()


def test_populated_state_rendering_all_pages(populated_repo_session):
    """Verify that all 11 pages render cleanly with populated analysis data."""
    for page in ALL_PAGES:
        try:
            page.render()
        except Exception as exc:
            pytest.fail(f"Populated-state rendering failed for {page.__name__}: {exc}")


def test_app_main_runs_without_crash(populated_repo_session):
    """Verify web.app.main() can be invoked without runtime exception."""
    try:
        app.main()
    except Exception as exc:
        pytest.fail(f"app.main() failed during execution: {exc}")
