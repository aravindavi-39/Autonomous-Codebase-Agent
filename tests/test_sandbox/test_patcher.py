"""Tests for SandboxPatcher: safety classification, path traversal, stale checks, and patch application."""

from pathlib import Path
import pytest

from refactoring.models import ChangeProposal, FileChange, SafetyClassification, TextEdit
from sandbox.copier import SandboxCopier
from sandbox.patcher import SandboxPatcher

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sandbox_test_repo"


@pytest.fixture
def sandbox_env(tmp_path):
    copier = SandboxCopier(temp_base_dir=tmp_path)
    sandbox_path = copier.create_sandbox(FIXTURE_DIR, "patcher_test_session")
    return sandbox_path


class TestSandboxPatcher:
    def test_rejects_review_required_proposal(self, sandbox_env):
        patcher = SandboxPatcher()
        proposal = ChangeProposal(
            finding_id="PAT-002_review",
            finding_type="PAT-002",
            strategy="WildcardImportStrategy",
            safety=SafetyClassification.REVIEW_REQUIRED,
            file_changes=[],
            description="Wildcard import",
            rationale="Review required",
            source_file="src/calculator.py",
            source_start_line=1,
            source_end_line=1,
        )
        res = patcher.apply_proposal(proposal, sandbox_env)
        assert res.success is False
        assert any("safety classification" in err.lower() for err in res.errors)

    def test_rejects_unsupported_proposal(self, sandbox_env):
        patcher = SandboxPatcher()
        proposal = ChangeProposal(
            finding_id="SMELL-001_long",
            finding_type="SMELL-001",
            strategy="LongFunctionStrategy",
            safety=SafetyClassification.UNSUPPORTED,
            file_changes=[],
            description="Long function",
            rationale="Manual refactoring",
            source_file="src/calculator.py",
            source_start_line=1,
            source_end_line=1,
        )
        res = patcher.apply_proposal(proposal, sandbox_env)
        assert res.success is False
        assert any("safety classification" in err.lower() for err in res.errors)

    def test_rejects_path_traversal(self, sandbox_env):
        patcher = SandboxPatcher()
        edit = TextEdit(start_line=1, end_line=1, original_text="x", replacement_text="y")
        proposal = ChangeProposal(
            finding_id="PAT-003_trav",
            finding_type="PAT-003",
            strategy="MutableDefaultStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            file_changes=[FileChange(file_path="../../outside.py", edits=[edit])],
            description="Traversal attempt",
            rationale="Test",
            source_file="src/calculator.py",
            source_start_line=1,
            source_end_line=1,
        )
        res = patcher.apply_proposal(proposal, sandbox_env)
        assert res.success is False
        assert any("traversal" in err.lower() or "escapes" in err.lower() for err in res.errors)

    def test_rejects_absolute_path(self, sandbox_env):
        patcher = SandboxPatcher()
        edit = TextEdit(start_line=1, end_line=1, original_text="x", replacement_text="y")
        proposal = ChangeProposal(
            finding_id="PAT-003_abs",
            finding_type="PAT-003",
            strategy="MutableDefaultStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            file_changes=[FileChange(file_path="C:/Windows/System32/evil.py", edits=[edit])],
            description="Absolute path attempt",
            rationale="Test",
            source_file="src/calculator.py",
            source_start_line=1,
            source_end_line=1,
        )
        res = patcher.apply_proposal(proposal, sandbox_env)
        assert res.success is False
        assert any("absolute" in err.lower() or "escapes" in err.lower() for err in res.errors)

    def test_rejects_stale_source_text(self, sandbox_env):
        patcher = SandboxPatcher()
        edit = TextEdit(
            start_line=6,
            end_line=6,
            original_text="def nonexistent_wrong_function():",
            replacement_text="def fixed():",
        )
        proposal = ChangeProposal(
            finding_id="PAT-003_stale",
            finding_type="PAT-003",
            strategy="MutableDefaultStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            file_changes=[FileChange(file_path="src/calculator.py", edits=[edit])],
            description="Stale patch attempt",
            rationale="Test",
            source_file="src/calculator.py",
            source_start_line=6,
            source_end_line=6,
        )
        res = patcher.apply_proposal(proposal, sandbox_env)
        assert res.success is False
        assert any("stale_proposal" in err.lower() for err in res.errors)

    def test_rejects_syntax_error_in_patch(self, sandbox_env):
        patcher = SandboxPatcher()
        # Original line 6 in calculator.py is: def add_entry(val, history=[]):
        orig_line = "def add_entry(val, history=[]):"
        edit = TextEdit(
            start_line=6,
            end_line=6,
            original_text=orig_line,
            replacement_text="def add_entry(val, history=None: def broken",  # Broken syntax
        )
        proposal = ChangeProposal(
            finding_id="PAT-003_syn",
            finding_type="PAT-003",
            strategy="MutableDefaultStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            file_changes=[FileChange(file_path="src/calculator.py", edits=[edit])],
            description="Syntax error patch",
            rationale="Test",
            source_file="src/calculator.py",
            source_start_line=6,
            source_end_line=6,
        )
        res = patcher.apply_proposal(proposal, sandbox_env)
        assert res.success is False
        assert any("syntax error" in err.lower() for err in res.errors)

    def test_successful_safe_patch_application(self, sandbox_env):
        patcher = SandboxPatcher()
        calc_file = sandbox_env / "src" / "calculator.py"
        lines = calc_file.read_text(encoding="utf-8").splitlines()
        
        # Line 6 is "def add_entry(val, history=[]):"
        line_num = 6
        orig_text = lines[line_num - 1]
        assert "add_entry(val, history=[])" in orig_text

        replacement_sig = "def add_entry(val, history=None):"
        # Body starts at line 8: "    history.append(val)"
        # We replace line 6 signature with replacement_sig
        edit1 = TextEdit(
            start_line=line_num,
            end_line=line_num,
            original_text=orig_text,
            replacement_text=replacement_sig,
        )
        # Line 8 is history.append(val)
        body_line_num = 8
        orig_body = lines[body_line_num - 1]
        rep_body = "    if history is None:\n        history = []\n" + orig_body
        edit2 = TextEdit(
            start_line=body_line_num,
            end_line=body_line_num,
            original_text=orig_body,
            replacement_text=rep_body,
        )

        proposal = ChangeProposal(
            finding_id="PAT-003_valid",
            finding_type="PAT-003",
            strategy="MutableDefaultStrategy",
            safety=SafetyClassification.SAFE_AUTOMATIC_PROPOSAL,
            file_changes=[FileChange(file_path="src/calculator.py", edits=[edit1, edit2])],
            description="Fix mutable default in calculator",
            rationale="Test",
            source_file="src/calculator.py",
            source_start_line=6,
            source_end_line=8,
        )

        res = patcher.apply_proposal(proposal, sandbox_env)
        assert res.success is True
        assert "src/calculator.py" in res.applied_files
        assert "--- a/src/calculator.py" in res.diff_applied
        assert "+def add_entry(val, history=None):" in res.diff_applied

        # Verify file content on disk in sandbox
        new_content = calc_file.read_text(encoding="utf-8")
        assert "history=None" in new_content
        assert "if history is None:" in new_content
