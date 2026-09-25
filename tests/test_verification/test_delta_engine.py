"""Tests for FindingDeltaEngine: evidence-based resolution, remaining findings, and new findings."""

import pytest

from analysis.findings.models import Confidence, Finding, FindingCategory, Severity
from verification.delta_engine import FindingDeltaEngine, findings_match


def _create_mock_finding(
    fid: str,
    ftype: str,
    file: str,
    line: int,
    entity: str = "func",
    evidence: str = "items=[]",
) -> Finding:
    return Finding(
        id=fid,
        category=FindingCategory.PATTERN,
        type=ftype,
        severity=Severity.LOW,
        confidence=Confidence.HIGH,
        title=f"Finding {fid}",
        description="Test description",
        rationale="Test rationale",
        file=file,
        start_line=line,
        end_line=line,
        entity=entity,
        evidence=evidence,
        recommendation="Fix it",
        analyzer_name="test",
    )


class TestFindingsMatch:
    def test_exact_id_matches(self):
        f1 = _create_mock_finding("PAT-003_1", "PAT-003", "src/a.py", 10)
        f2 = _create_mock_finding("PAT-003_1", "PAT-003", "src/a.py", 10)
        assert findings_match(f1, f2) is True

    def test_line_shift_same_entity_matches(self):
        f1 = _create_mock_finding("PAT-003_1", "PAT-003", "src/a.py", 10, entity="my_func")
        f2 = _create_mock_finding("PAT-003_2", "PAT-003", "src/a.py", 14, entity="my_func")
        assert findings_match(f1, f2) is True

    def test_different_type_or_file_does_not_match(self):
        f1 = _create_mock_finding("PAT-003_1", "PAT-003", "src/a.py", 10)
        f2 = _create_mock_finding("PAT-002_1", "PAT-002", "src/a.py", 10)
        f3 = _create_mock_finding("PAT-003_3", "PAT-003", "src/b.py", 10)
        assert findings_match(f1, f2) is False
        assert findings_match(f1, f3) is False


class TestFindingDeltaEngine:
    def test_target_finding_resolved_successfully(self):
        engine = FindingDeltaEngine()
        target_id = "PAT-003_target"
        f_target = _create_mock_finding(target_id, "PAT-003", "src/a.py", 10, entity="target_func")
        f_other = _create_mock_finding("PAT-005_other", "PAT-005", "src/a.py", 2, entity="sys")

        baseline = [f_target, f_other]
        # In post-patch, target is gone, other remains
        post_patch = [f_other]

        delta = engine.compute_delta(baseline, post_patch, target_finding_id=target_id)
        assert delta.target_existed_in_baseline is True
        assert delta.target_resolved is True
        assert len(delta.resolved_findings) == 1
        assert delta.resolved_findings[0].id == target_id
        assert len(delta.remaining_findings) == 1
        assert len(delta.new_findings) == 0

    def test_unchanged_finding_remains_unresolved(self):
        engine = FindingDeltaEngine()
        target_id = "PAT-003_unresolved"
        f_target = _create_mock_finding(target_id, "PAT-003", "src/a.py", 10, entity="target_func")

        baseline = [f_target]
        post_patch = [f_target]  # Still present!

        delta = engine.compute_delta(baseline, post_patch, target_finding_id=target_id)
        assert delta.target_existed_in_baseline is True
        assert delta.target_resolved is False
        assert len(delta.resolved_findings) == 0
        assert len(delta.remaining_findings) == 1
        assert len(delta.new_findings) == 0

    def test_genuinely_new_finding_distinguished_from_pre_existing(self):
        engine = FindingDeltaEngine()
        f_base = _create_mock_finding("PAT-005_base", "PAT-005", "src/a.py", 2, entity="os")
        f_new = _create_mock_finding("SMELL-001_new", "SMELL-001", "src/a.py", 50, entity="huge_func")

        baseline = [f_base]
        post_patch = [f_base, f_new]

        delta = engine.compute_delta(baseline, post_patch)
        assert len(delta.resolved_findings) == 0
        assert len(delta.remaining_findings) == 1
        assert len(delta.new_findings) == 1
        assert delta.new_findings[0].id == "SMELL-001_new"

    def test_pre_existing_finding_with_line_shift_not_falsely_new(self):
        engine = FindingDeltaEngine()
        # Baseline finding on line 10
        f_base = _create_mock_finding("PAT-003_base", "PAT-003", "src/a.py", 10, entity="some_func")
        # Post-patch has the same finding now shifted to line 12 because 2 lines were added above
        f_shifted = _create_mock_finding("PAT-003_shifted", "PAT-003", "src/a.py", 12, entity="some_func")

        baseline = [f_base]
        post_patch = [f_shifted]

        delta = engine.compute_delta(baseline, post_patch)
        assert len(delta.resolved_findings) == 0
        assert len(delta.remaining_findings) == 1
        assert len(delta.new_findings) == 0  # NOT falsely classified as new!
