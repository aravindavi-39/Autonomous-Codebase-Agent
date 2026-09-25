"""Tests for DiffGenerator: diff generation from proposals, TextEdit application, unified diff format."""

import hashlib
from pathlib import Path

import pytest

from analysis.analyzer import RepositoryAnalyzer
from analysis.findings.context import AnalysisContext
from analysis.findings.engine import AnalysisEngine
from analysis.graph_builder import CodeGraphBuilder
from ingestion.pipeline import IngestionPipeline
from refactoring.generator import DiffGenerator
from refactoring.models import ChangeProposal, DiffResult, FileChange, SafetyClassification, TextEdit
from refactoring.planner import RefactoringPlanner

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "vulnerable_repo"


def _hash_directory(directory: Path) -> str:
    """Compute a deterministic hash of all files in directory."""
    hasher = hashlib.sha256()
    for file_path in sorted(directory.rglob("*")):
        if file_path.is_file() and "__pycache__" not in str(file_path):
            hasher.update(str(file_path.relative_to(directory)).encode())
            hasher.update(file_path.read_bytes())
    return hasher.hexdigest()


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


class TestDiffGenerator:
    def test_generate_safe_diffs(self, full_context):
        """Generate diffs for safe proposals and verify unified diff format."""
        context, report = full_context
        planner = RefactoringPlanner()
        plan = planner.plan(report=report, context=context, safe_only=True)

        generator = DiffGenerator()
        generated_any = False

        for action in plan.actions:
            if action.proposal.file_changes:
                diff_results = generator.generate(action.proposal, context)
                for diff_result in diff_results:
                    assert isinstance(diff_result, DiffResult)
                    assert diff_result.file_path
                    assert diff_result.unified_diff
                    # Valid unified diff should have --- and +++ headers
                    assert "---" in diff_result.unified_diff
                    assert "+++" in diff_result.unified_diff
                    generated_any = True

        assert generated_any, "Expected at least one diff to be generated for safe proposals"

    def test_generate_from_manual_proposal(self, full_context):
        """Generate diff from a manually constructed proposal."""
        context, _ = full_context
        edit = TextEdit(
            start_line=3,
            end_line=3,
            original_text="from math import *",
            replacement_text="from math import sqrt, pi",
        )
        proposal = ChangeProposal(
            finding_id="TEST_manual",
            finding_type="PAT-002",
            strategy="TestStrategy",
            safety=SafetyClassification.REVIEW_REQUIRED,
            file_changes=[FileChange(file_path="src/patterns.py", edits=[edit])],
            description="Replace wildcard import",
            rationale="Explicit imports",
            source_file="src/patterns.py",
            source_start_line=3,
            source_end_line=3,
        )

        generator = DiffGenerator()
        diff_results = generator.generate(proposal, context)
        assert len(diff_results) == 1
        diff = diff_results[0]
        assert "from math import *" in diff.unified_diff or "-from math import *" in diff.unified_diff

    def test_empty_proposal_returns_no_diffs(self, full_context):
        """Proposal with no file changes returns empty list."""
        context, _ = full_context
        proposal = ChangeProposal(
            finding_id="TEST_empty",
            finding_type="PAT-001",
            strategy="TestStrategy",
            safety=SafetyClassification.REVIEW_REQUIRED,
            file_changes=[],
            description="No changes",
            rationale="Advisory only",
            source_file="src/patterns.py",
            source_start_line=1,
            source_end_line=1,
        )

        generator = DiffGenerator()
        diff_results = generator.generate(proposal, context)
        assert len(diff_results) == 0

    def test_apply_edits_bottom_to_top(self):
        """Verify edits are applied from bottom to top to preserve line numbers."""
        generator = DiffGenerator()
        lines = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
        edits = [
            TextEdit(start_line=2, end_line=2, original_text="line2", replacement_text="modified2"),
            TextEdit(start_line=4, end_line=4, original_text="line4", replacement_text="modified4"),
        ]
        result = generator._apply_edits(lines, edits)
        assert "modified2\n" in result
        assert "modified4\n" in result
        assert len(result) == 5  # Same number of lines

    def test_deletion_edit(self):
        """Verify empty replacement_text deletes lines."""
        generator = DiffGenerator()
        lines = ["line1\n", "line2\n", "line3\n"]
        edits = [
            TextEdit(start_line=2, end_line=2, original_text="line2", replacement_text=""),
        ]
        result = generator._apply_edits(lines, edits)
        assert len(result) == 2
        assert "line2" not in "".join(result)

    def test_repository_immutability(self, full_context):
        """Verify generating diffs does NOT modify the original repository."""
        hash_before = _hash_directory(FIXTURE_DIR)

        context, report = full_context
        planner = RefactoringPlanner()
        plan = planner.plan(report=report, context=context, safe_only=True)

        generator = DiffGenerator()
        for action in plan.actions:
            if action.proposal.file_changes:
                generator.generate(action.proposal, context)

        hash_after = _hash_directory(FIXTURE_DIR)
        assert hash_before == hash_after, "Original repository was modified during diff generation!"
