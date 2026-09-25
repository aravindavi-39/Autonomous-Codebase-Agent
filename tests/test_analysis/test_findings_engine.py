"""Tests for the AnalysisEngine orchestration, safety, and filtering."""

import hashlib
from pathlib import Path
import pytest

from ingestion.pipeline import IngestionPipeline
from analysis.analyzer import RepositoryAnalyzer
from analysis.graph_builder import CodeGraphBuilder
from analysis.findings.engine import AnalysisEngine
from analysis.findings.models import Severity, FindingCategory


def hash_directory_files(repo_path: Path) -> dict[str, str]:
    """Calculate SHA256 hashes of all files in directory."""
    hashes = {}
    for p in repo_path.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            hashes[str(p.relative_to(repo_path))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


@pytest.fixture
def vulnerable_repo_data():
    repo_path = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(repo_path))
    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(repo_path))
    builder = CodeGraphBuilder()
    graph = builder.build_graph(code_index)
    return repo_path, manifest, code_index, graph


def test_engine_run_on_vulnerable_repo(vulnerable_repo_data):
    repo_path, manifest, code_index, graph = vulnerable_repo_data
    
    # Hash before
    hashes_before = hash_directory_files(repo_path)
    
    engine = AnalysisEngine()
    report = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=graph,
        root_path=repo_path,
    )
    
    # Hash after: verify strict read-only guarantee
    hashes_after = hash_directory_files(repo_path)
    assert hashes_before == hashes_after, "Repository files were modified during analysis!"
    
    assert report.files_analyzed >= 4
    assert len(report.findings) > 0
    assert report.summary["total"] == len(report.findings)
    
    # Check that findings have valid line numbers and locations
    file_map = {f.relative_path.replace("\\", "/"): f for f in manifest.files}
    
    for f in report.findings:
        assert f.start_line >= 1
        assert f.end_line >= f.start_line
        assert f.file in file_map, f"Finding file path {f.file} not in repository manifest"
        
        # Check evidence is populated
        if f.evidence:
            assert len(f.evidence) > 0


def test_engine_category_filtering(vulnerable_repo_data):
    repo_path, manifest, code_index, graph = vulnerable_repo_data
    engine = AnalysisEngine()
    
    # Disable security rules
    report_no_sec = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=graph,
        root_path=repo_path,
        enable_security=False,
    )
    assert not any(f.category == FindingCategory.SECURITY for f in report_no_sec.findings)
    assert any(f.category == FindingCategory.CODE_SMELL for f in report_no_sec.findings)
    assert any(f.category == FindingCategory.PATTERN for f in report_no_sec.findings)
    
    # Disable smells
    report_no_smells = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=graph,
        root_path=repo_path,
        enable_smells=False,
    )
    assert not any(f.category == FindingCategory.CODE_SMELL for f in report_no_smells.findings)
    assert any(f.category == FindingCategory.SECURITY for f in report_no_smells.findings)
    
    # Disable patterns
    report_no_patterns = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=graph,
        root_path=repo_path,
        enable_patterns=False,
    )
    assert not any(f.category == FindingCategory.PATTERN for f in report_no_patterns.findings)


def test_engine_severity_filtering(vulnerable_repo_data):
    repo_path, manifest, code_index, graph = vulnerable_repo_data
    engine = AnalysisEngine()
    
    report = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=graph,
        root_path=repo_path,
        min_severity=Severity.HIGH,
    )
    
    for f in report.findings:
        assert f.severity in (Severity.HIGH, Severity.CRITICAL)


def test_engine_on_clean_sample_repo():
    repo_path = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(repo_path))
    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(repo_path))
    builder = CodeGraphBuilder()
    graph = builder.build_graph(code_index)
    
    engine = AnalysisEngine()
    report = engine.analyze(
        manifest=manifest,
        code_index=code_index,
        code_graph=graph,
        root_path=repo_path,
    )
    
    # Sample repo is clean, should have 0 critical and 0 high security vulnerabilities
    crit_or_high_sec = [
        f for f in report.findings
        if f.category == FindingCategory.SECURITY and f.severity in (Severity.CRITICAL, Severity.HIGH)
    ]
    assert len(crit_or_high_sec) == 0
