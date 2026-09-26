"""Regression tests for previously identified Web UI API incompatibilities.

Ensures the Web UI pages correctly interact with:
1. `CodeGraph.statistics` (and does NOT call non-existent `compute_statistics()`)
2. `RepositoryCodeIndex.get_classes()` (and does NOT access non-existent `.classes`)
3. `RepositoryCodeIndex.get_functions()` (and does NOT access non-existent `.functions`)
"""

from __future__ import annotations

from pathlib import Path
import pytest

from analysis.analyzer import RepositoryAnalyzer
from analysis.graph_builder import CodeGraphBuilder
from analysis.graph_models import CodeGraph
from analysis.models import RepositoryCodeIndex
from ingestion.pipeline import IngestionPipeline
import web.pages.architecture as page_architecture
import web.pages.code_understanding as page_code_understanding
import web.pages.dashboard as page_dashboard
import web.state as state


@pytest.fixture
def populated_session(tmp_path: Path):
    """Load and index sandbox_test_repo into session state."""
    repo_path = Path("tests/fixtures/sandbox_test_repo").resolve()
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(repo_path))

    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(repo_path), manifest=manifest)

    builder = CodeGraphBuilder()
    code_graph = builder.build_graph(code_index)

    state.reset_session_cache()
    state.set_repo_path(str(repo_path))
    state.set_manifest(manifest)
    state.set_code_index(code_index)
    state.set_code_graph(code_graph)

    yield {
        "manifest": manifest,
        "code_index": code_index,
        "code_graph": code_graph,
    }
    state.reset_session_cache()


def test_codegraph_statistics_api_contract(populated_session):
    """Verify CodeGraph exposes .statistics attribute and NOT compute_statistics()."""
    code_graph: CodeGraph = populated_session["code_graph"]
    assert hasattr(code_graph, "statistics"), "CodeGraph must have 'statistics' attribute"
    assert not hasattr(code_graph, "compute_statistics"), "CodeGraph should NOT have 'compute_statistics' method"
    assert code_graph.statistics.total_nodes > 0
    assert code_graph.statistics.total_edges >= 0


def test_code_index_classes_api_contract(populated_session):
    """Verify RepositoryCodeIndex exposes get_classes() method and NOT .classes attribute."""
    code_index: RepositoryCodeIndex = populated_session["code_index"]
    assert hasattr(code_index, "get_classes"), "RepositoryCodeIndex must have 'get_classes' method"
    assert not hasattr(code_index, "classes"), "RepositoryCodeIndex should NOT have 'classes' attribute"
    classes = code_index.get_classes()
    assert isinstance(classes, list)


def test_code_index_functions_api_contract(populated_session):
    """Verify RepositoryCodeIndex exposes get_functions() method and NOT .functions attribute."""
    code_index: RepositoryCodeIndex = populated_session["code_index"]
    assert hasattr(code_index, "get_functions"), "RepositoryCodeIndex must have 'get_functions' method"
    assert not hasattr(code_index, "functions"), "RepositoryCodeIndex should NOT have 'functions' attribute"
    funcs = code_index.get_functions()
    assert isinstance(funcs, list)


def test_architecture_page_renders_with_real_index_and_graph(populated_session):
    """Exercise web.pages.architecture.render() against real models without AttributeError."""
    try:
        page_architecture.render()
    except AttributeError as exc:
        pytest.fail(f"page_architecture.render() raised AttributeError: {exc}")


def test_dashboard_page_renders_with_real_index(populated_session):
    """Exercise web.pages.dashboard.render() against real models without AttributeError."""
    try:
        page_dashboard.render()
    except AttributeError as exc:
        pytest.fail(f"page_dashboard.render() raised AttributeError: {exc}")


def test_code_understanding_page_renders_with_real_index(populated_session):
    """Exercise web.pages.code_understanding.render() against real models without AttributeError."""
    try:
        page_code_understanding.render()
    except AttributeError as exc:
        pytest.fail(f"page_code_understanding.render() raised AttributeError: {exc}")
