"""Tests for SandboxCopier: isolated cloning, directory exclusion, and symlink protection."""

from pathlib import Path
import pytest

from sandbox.copier import SandboxCopier, compute_directory_fingerprint

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sandbox_test_repo"


class TestSandboxCopier:
    def test_compute_fingerprint_is_deterministic(self):
        fp1 = compute_directory_fingerprint(FIXTURE_DIR)
        fp2 = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex string

    def test_create_sandbox_copies_files(self, tmp_path):
        copier = SandboxCopier(temp_base_dir=tmp_path)
        session_id = "test_copier_001"
        sandbox_path = copier.create_sandbox(FIXTURE_DIR, session_id)

        assert sandbox_path.exists()
        assert sandbox_path.is_dir()
        assert (sandbox_path / "src" / "calculator.py").exists()
        assert (sandbox_path / "tests" / "test_calculator.py").exists()

        # Check content match
        src_text = (FIXTURE_DIR / "src" / "calculator.py").read_text(encoding="utf-8")
        copied_text = (sandbox_path / "src" / "calculator.py").read_text(encoding="utf-8")
        assert src_text == copied_text

    def test_create_sandbox_excludes_ignored_directories(self, tmp_path):
        # Create a mock repo with __pycache__ and .git
        mock_repo = tmp_path / "mock_repo"
        mock_repo.mkdir()
        (mock_repo / "main.py").write_text("print('hello')")
        (mock_repo / ".git").mkdir()
        (mock_repo / ".git" / "config").write_text("git config")
        (mock_repo / "__pycache__").mkdir()
        (mock_repo / "__pycache__" / "main.cpython.pyc").write_text("bytecode")

        copier = SandboxCopier(temp_base_dir=tmp_path / "sandboxes")
        sandbox_path = copier.create_sandbox(mock_repo, "session_ignore_check")

        assert (sandbox_path / "main.py").exists()
        assert not (sandbox_path / ".git").exists()
        assert not (sandbox_path / "__pycache__").exists()

    def test_create_sandbox_rejects_nonexistent_source(self, tmp_path):
        copier = SandboxCopier(temp_base_dir=tmp_path)
        with pytest.raises(ValueError, match="does not exist"):
            copier.create_sandbox(tmp_path / "nonexistent_repo", "fail_session")

    def test_source_remains_intact_after_copy(self, tmp_path):
        fp_before = compute_directory_fingerprint(FIXTURE_DIR)
        copier = SandboxCopier(temp_base_dir=tmp_path)
        copier.create_sandbox(FIXTURE_DIR, "session_intact")
        fp_after = compute_directory_fingerprint(FIXTURE_DIR)
        assert fp_before == fp_after
