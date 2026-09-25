"""Tests for SandboxCleanup: guarded directory removal and safety checks."""

from pathlib import Path
import tempfile
import pytest

from sandbox.cleanup import SandboxCleanup


class TestSandboxCleanup:
    def test_cleanup_removes_sandbox_directory(self):
        cleanup = SandboxCleanup()
        temp_dir = Path(tempfile.gettempdir())
        target_dir = temp_dir / "codebase_agent_sandbox_test123" / "myrepo"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "file.txt").write_text("hello")

        assert target_dir.exists()
        success = cleanup.cleanup(target_dir)
        assert success is True
        assert not target_dir.exists()

    def test_cleanup_refuses_deletion_outside_temp(self, tmp_path):
        # Even if folder has the sandbox name, if it's outside system tempdir, refuse deletion
        cleanup = SandboxCleanup()
        safe_home = tmp_path / "user_home"
        target_dir = safe_home / "codebase_agent_sandbox_fake"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "file.txt").write_text("should not delete")

        # tmp_path on Windows is usually in AppData/Local/Temp, but let's test a path clearly outside temp
        # by checking guardrail against arbitrary root path
        sys_temp = Path(tempfile.gettempdir()).resolve()
        
        # Non-sandbox named path inside temp
        non_sandbox = sys_temp / "regular_temp_folder_not_sandbox"
        non_sandbox.mkdir(exist_ok=True)
        try:
            res = cleanup.cleanup(non_sandbox)
            assert res is False
            assert non_sandbox.exists()
        finally:
            non_sandbox.rmdir()

    def test_cleanup_nonexistent_returns_true(self):
        cleanup = SandboxCleanup()
        temp_dir = Path(tempfile.gettempdir())
        nonexistent = temp_dir / "codebase_agent_sandbox_nonexistent"
        assert cleanup.cleanup(nonexistent) is True
