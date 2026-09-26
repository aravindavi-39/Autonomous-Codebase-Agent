"""Automated tests for Phase 8.1 Streamlit Web UI components and safety guarantees."""

from __future__ import annotations

import inspect
from pathlib import Path
import pytest

from analysis.findings.models import FindingCategory, Severity
from citations.models import Citation
from ingestion.validator import ValidationError, validate_repository_path
from refactoring.models import ChangeProposal, SafetyClassification
from sandbox.copier import compute_directory_fingerprint
from sandbox.manager import SandboxManager
from sandbox.models import ApprovalStatus
import web.app as web_app


def test_web_app_import() -> None:
    """web.app must import cleanly when Streamlit is installed."""
    assert hasattr(web_app, "main")
    assert hasattr(web_app, "get_severity_badge_color")
    assert hasattr(web_app, "get_safety_badge_color")
    assert hasattr(web_app, "format_citation_markdown")


def test_severity_badge_colors() -> None:
    """Ensure every Finding Severity maps to a valid hex color string."""
    for sev in Severity:
        color = web_app.get_severity_badge_color(sev)
        assert color.startswith("#")
        assert len(color) == 7


def test_safety_badge_colors() -> None:
    """Ensure every Refactoring Safety Classification maps to an appropriate badge color."""
    for safety in SafetyClassification:
        color = web_app.get_safety_badge_color(safety)
        assert color.startswith("#")
        assert len(color) == 7

    # Green for safe automatic proposal
    assert web_app.get_safety_badge_color(SafetyClassification.SAFE_AUTOMATIC_PROPOSAL) == "#2e7d32"


def test_citation_formatting() -> None:
    """Test citation markdown formatting with and without entity names."""
    cit_with_entity = Citation(
        file="src/calculator.py",
        start_line=6,
        end_line=9,
        entity="add_entry",
        snippet="def add_entry(val, history=[]):",
    )
    formatted = web_app.format_citation_markdown(cit_with_entity)
    assert "src/calculator.py:6-9" in formatted
    assert "(add_entry)" in formatted

    cit_no_entity = Citation(
        file="src/utils.py",
        start_line=1,
        end_line=5,
        entity=None,
        snippet="import os",
    )
    formatted_no_ent = web_app.format_citation_markdown(cit_no_entity)
    assert "src/utils.py:1-5" in formatted_no_ent
    assert "(" not in formatted_no_ent


def test_path_validation_rejection() -> None:
    """Ensure invalid and non-existent paths are rejected with ValidationError."""
    with pytest.raises(ValidationError):
        validate_repository_path("non_existent_directory_xyz_12345")

    with pytest.raises(ValidationError):
        validate_repository_path("")


def test_target_immutability_during_analysis() -> None:
    """Target fixture repository must remain 100% byte-for-byte unchanged during analysis."""
    repo_path = Path("tests/fixtures/sandbox_test_repo").resolve()
    pre_hash = compute_directory_fingerprint(repo_path)

    # Perform full analysis cycle as executed by the web UI
    from ingestion.pipeline import IngestionPipeline
    from analysis.analyzer import RepositoryAnalyzer
    from analysis.graph_builder import CodeGraphBuilder
    from analysis.findings.engine import AnalysisEngine
    from analysis.findings.context import AnalysisContext
    from refactoring.planner import RefactoringPlanner

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

    context = AnalysisContext(manifest=manifest, code_index=code_index, code_graph=code_graph)
    planner = RefactoringPlanner()
    plan = planner.plan(report=report, context=context)

    assert manifest is not None
    assert code_index is not None
    assert code_graph is not None
    assert report is not None
    assert plan is not None

    post_hash = compute_directory_fingerprint(repo_path)
    assert pre_hash == post_hash, "Target repository was modified during analysis operations!"


def test_approval_boundary_enforced() -> None:
    """Sandbox application must reject session if approved is False."""
    repo_path = Path("tests/fixtures/sandbox_test_repo").resolve()
    dummy_proposal = ChangeProposal(
        finding_id="PAT-003_dummy",
        finding_type="PAT-003",
        strategy="MutableDefaultStrategy",
        safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
        file_changes=[],
        description="Dummy safe proposal for approval testing",
        rationale="Testing approval gate",
        source_file="src/calculator.py",
        source_start_line=6,
        source_end_line=6,
    )

    manager = SandboxManager()
    report = manager.execute_session(
        source_path=repo_path,
        proposal=dummy_proposal,
        approved=False,
    )
    assert report.session.approval_status == ApprovalStatus.REJECTED
    assert any("Explicit approval is required" in err for err in report.session.errors)


def test_no_secrets_in_web_app_source() -> None:
    """web/app.py source code must not contain hardcoded credentials or API tokens."""
    source_code = inspect.getsource(web_app)
    forbidden_terms = [
        "sk-proj-",
        "ghp_",
        "AWS_SECRET_ACCESS_KEY",
        "AKIA",
        "Bearer ",
    ]
    for term in forbidden_terms:
        assert term not in source_code, f"Suspicious credential token found in web/app.py: {term}"


def test_file_record_metadata_access() -> None:
    """Ensure FileRecord lines and size are retrieved through .metadata without AttributeError."""
    from ingestion.models import FileMetadata, FileRecord, Language

    record = FileRecord(
        relative_path="src/calculator.py",
        file_name="calculator.py",
        extension=".py",
        language=Language.PYTHON,
        metadata=FileMetadata(size_bytes=512, line_count=24, is_binary=False),
    )
    # Validate the exact mapping used in web/app.py
    display_item = {
        "Relative Path": record.relative_path,
        "Language": record.language.value if hasattr(record.language, "value") else str(record.language),
        "Lines": record.metadata.line_count,
        "Size": f"{record.metadata.size_bytes} B",
    }
    assert display_item["Lines"] == 24
    assert display_item["Size"] == "512 B"
    assert display_item["Language"] == "Python"

