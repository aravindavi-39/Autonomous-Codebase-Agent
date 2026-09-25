"""Tests for refactoring strategies: can_handle, propose, and edge cases.

All strategies are deterministic — no LLM calls.
Tests use the existing vulnerable_repo fixture.
"""

import hashlib
from pathlib import Path

import pytest

from analysis.analyzer import RepositoryAnalyzer
from analysis.findings.context import AnalysisContext
from analysis.findings.engine import AnalysisEngine
from analysis.findings.models import (
    AnalysisReport,
    Confidence,
    Finding,
    FindingCategory,
    Severity,
)
from analysis.graph_builder import CodeGraphBuilder
from ingestion.pipeline import IngestionPipeline
from refactoring.models import SafetyClassification
from refactoring.strategies import (
    BroadExceptionStrategy,
    DebugTrueStrategy,
    HighParameterCountStrategy,
    LongFunctionStrategy,
    MutableDefaultStrategy,
    StrategyRegistry,
    UnusedImportStrategy,
    WeakCryptoStrategy,
    WildcardImportStrategy,
    get_default_strategy_registry,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"


def _make_finding(**overrides):
    defaults = dict(
        id="TEST_abcd1234",
        category=FindingCategory.PATTERN,
        type="PAT-003",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        title="Test Finding",
        description="Test description.",
        rationale="Test rationale.",
        file="src/patterns.py",
        start_line=14,
        end_line=14,
        recommendation="Fix it.",
    )
    defaults.update(overrides)
    return Finding(**defaults)


@pytest.fixture(scope="module")
def analysis_context():
    """Build a full analysis context from the vulnerable_repo fixture."""
    pipeline = IngestionPipeline()
    manifest = pipeline.ingest(str(FIXTURE_DIR))
    analyzer = RepositoryAnalyzer()
    code_index = analyzer.analyze_repository(str(FIXTURE_DIR), manifest=manifest)
    builder = CodeGraphBuilder()
    code_graph = builder.build_graph(code_index)
    return AnalysisContext(
        manifest=manifest,
        code_index=code_index,
        code_graph=code_graph,
    )


@pytest.fixture(scope="module")
def analysis_report(analysis_context):
    """Run AnalysisEngine on the vulnerable_repo fixture."""
    engine = AnalysisEngine()
    return engine.analyze(
        manifest=analysis_context.manifest,
        code_index=analysis_context.code_index,
        code_graph=analysis_context.code_graph,
    )


# ───── Strategy Registry ─────


class TestStrategyRegistry:
    def test_default_registry_has_all_strategies(self):
        registry = get_default_strategy_registry()
        strategies = registry.all_strategies()
        names = {s.strategy_name for s in strategies}
        assert "MutableDefaultStrategy" in names
        assert "WildcardImportStrategy" in names
        assert "BroadExceptionStrategy" in names
        assert "LongFunctionStrategy" in names
        assert "HighParameterCountStrategy" in names
        assert "UnusedImportStrategy" in names
        assert "DebugTrueStrategy" in names
        assert "WeakCryptoStrategy" in names

    def test_lookup_by_finding_type(self):
        registry = get_default_strategy_registry()
        finding = _make_finding(type="PAT-003")
        strategy = registry.get_strategy(finding)
        assert strategy is not None
        assert strategy.strategy_name == "MutableDefaultStrategy"

    def test_unknown_type_returns_none(self):
        registry = get_default_strategy_registry()
        finding = _make_finding(type="UNKNOWN-999")
        assert registry.get_strategy(finding) is None


# ───── Strategy A: Mutable Default ─────


class TestMutableDefaultStrategy:
    def test_can_handle(self):
        strategy = MutableDefaultStrategy()
        assert strategy.can_handle(_make_finding(type="PAT-003"))
        assert not strategy.can_handle(_make_finding(type="PAT-001"))

    def test_propose_on_vulnerable_repo(self, analysis_context, analysis_report):
        """PAT-003 should be detected in vulnerable_repo/src/patterns.py (append_to_list)."""
        strategy = MutableDefaultStrategy()
        pat003_findings = [f for f in analysis_report.findings if f.type == "PAT-003"]
        assert len(pat003_findings) > 0, "Expected at least one PAT-003 finding"

        for finding in pat003_findings:
            proposal = strategy.propose(finding, analysis_context)
            assert proposal.finding_id == finding.id
            assert proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
            assert proposal.strategy == "MutableDefaultStrategy"
            # Safe proposals for mutable defaults should have file changes
            if proposal.file_changes:
                assert any("None" in e.replacement_text for fc in proposal.file_changes for e in fc.edits)


# ───── Strategy B: Wildcard Import ─────


class TestWildcardImportStrategy:
    def test_can_handle(self):
        strategy = WildcardImportStrategy()
        assert strategy.can_handle(_make_finding(type="PAT-002"))
        assert not strategy.can_handle(_make_finding(type="PAT-003"))

    def test_propose_is_review_required(self, analysis_context, analysis_report):
        strategy = WildcardImportStrategy()
        pat002_findings = [f for f in analysis_report.findings if f.type == "PAT-002"]
        assert len(pat002_findings) > 0, "Expected at least one PAT-002 finding"

        for finding in pat002_findings:
            proposal = strategy.propose(finding, analysis_context)
            assert proposal.safety == SafetyClassification.REVIEW_REQUIRED
            assert not proposal.file_changes  # No auto-changes for review-required


# ───── Strategy C: Broad Exception ─────


class TestBroadExceptionStrategy:
    def test_can_handle(self):
        strategy = BroadExceptionStrategy()
        assert strategy.can_handle(_make_finding(type="PAT-001"))

    def test_propose_is_review_required(self, analysis_context, analysis_report):
        strategy = BroadExceptionStrategy()
        pat001_findings = [f for f in analysis_report.findings if f.type == "PAT-001"]
        assert len(pat001_findings) > 0, "Expected at least one PAT-001 finding"

        for finding in pat001_findings:
            proposal = strategy.propose(finding, analysis_context)
            assert proposal.safety == SafetyClassification.REVIEW_REQUIRED
            assert not proposal.file_changes


# ───── Strategy D: Long Function ─────


class TestLongFunctionStrategy:
    def test_can_handle(self):
        strategy = LongFunctionStrategy()
        assert strategy.can_handle(_make_finding(type="SMELL-001"))

    def test_propose_is_unsupported(self, analysis_context, analysis_report):
        strategy = LongFunctionStrategy()
        smell001_findings = [f for f in analysis_report.findings if f.type == "SMELL-001"]
        assert len(smell001_findings) > 0, "Expected at least one SMELL-001 finding"

        proposal = strategy.propose(smell001_findings[0], analysis_context)
        assert proposal.safety == SafetyClassification.UNSUPPORTED
        assert not proposal.file_changes


# ───── Strategy E: High Parameter Count ─────


class TestHighParameterCountStrategy:
    def test_can_handle(self):
        strategy = HighParameterCountStrategy()
        assert strategy.can_handle(_make_finding(type="SMELL-002"))

    def test_propose_is_unsupported(self, analysis_context, analysis_report):
        strategy = HighParameterCountStrategy()
        smell002_findings = [f for f in analysis_report.findings if f.type == "SMELL-002"]
        assert len(smell002_findings) > 0, "Expected at least one SMELL-002 finding"

        proposal = strategy.propose(smell002_findings[0], analysis_context)
        assert proposal.safety == SafetyClassification.UNSUPPORTED
        assert not proposal.file_changes


# ───── Strategy F: Unused Import ─────


class TestUnusedImportStrategy:
    def test_can_handle(self):
        strategy = UnusedImportStrategy()
        assert strategy.can_handle(_make_finding(type="PAT-005"))

    def test_propose_removes_import(self, analysis_context, analysis_report):
        """PAT-005 should be detected for unused 'sys' import in patterns.py."""
        strategy = UnusedImportStrategy()
        pat005_findings = [f for f in analysis_report.findings if f.type == "PAT-005"]
        assert len(pat005_findings) > 0, "Expected at least one PAT-005 finding"

        for finding in pat005_findings:
            proposal = strategy.propose(finding, analysis_context)
            assert proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
            assert proposal.finding_id == finding.id
            # Should have file changes (removal of import line)
            if proposal.file_changes:
                assert len(proposal.file_changes) > 0


# ───── Strategy G: Debug True ─────


class TestDebugTrueStrategy:
    def test_can_handle(self):
        strategy = DebugTrueStrategy()
        assert strategy.can_handle(_make_finding(type="SEC-010"))

    def test_propose_replaces_debug(self, analysis_context, analysis_report):
        """SEC-010 should be detected for debug=True in security.py."""
        strategy = DebugTrueStrategy()
        sec010_findings = [f for f in analysis_report.findings if f.type == "SEC-010"]
        assert len(sec010_findings) > 0, "Expected at least one SEC-010 finding"

        for finding in sec010_findings:
            proposal = strategy.propose(finding, analysis_context)
            assert proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
            if proposal.file_changes:
                for fc in proposal.file_changes:
                    for edit in fc.edits:
                        assert "debug=False" in edit.replacement_text or "DEBUG = False" in edit.replacement_text


# ───── Strategy H: Weak Crypto ─────


class TestWeakCryptoStrategy:
    def test_can_handle(self):
        strategy = WeakCryptoStrategy()
        assert strategy.can_handle(_make_finding(type="SEC-008"))

    def test_propose_is_review_required(self, analysis_context, analysis_report):
        """SEC-008 should be detected for MD5/SHA1 in security.py."""
        strategy = WeakCryptoStrategy()
        sec008_findings = [f for f in analysis_report.findings if f.type == "SEC-008"]
        assert len(sec008_findings) > 0, "Expected at least one SEC-008 finding"

        for finding in sec008_findings:
            proposal = strategy.propose(finding, analysis_context)
            assert proposal.safety == SafetyClassification.REVIEW_REQUIRED
            assert not proposal.file_changes
