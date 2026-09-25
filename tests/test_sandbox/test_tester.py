"""Tests for SandboxTester: pytest execution, framework detection, env sanitization, and timeout."""

from pathlib import Path
import pytest

from sandbox.copier import SandboxCopier
from sandbox.tester import SandboxTester

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sandbox_test_repo"


@pytest.fixture
def sandbox_env(tmp_path):
    copier = SandboxCopier(temp_base_dir=tmp_path)
    return copier.create_sandbox(FIXTURE_DIR, "tester_session")


class TestSandboxTester:
    def test_has_tests_detects_fixture_tests(self, sandbox_env):
        tester = SandboxTester()
        assert tester.has_tests(sandbox_env) is True

    def test_has_tests_returns_false_for_empty(self, tmp_path):
        tester = SandboxTester()
        empty_dir = tmp_path / "empty_repo"
        empty_dir.mkdir()
        assert tester.has_tests(empty_dir) is False

    def test_run_tests_success(self, sandbox_env):
        tester = SandboxTester(timeout_seconds=30)
        res = tester.run_tests(sandbox_env)
        assert res.status == "PASSED"
        assert res.return_code == 0
        assert res.passed == 2
        assert res.failed == 0
        assert "passed" in res.summary

    def test_run_tests_empty_repo_reports_no_tests(self, tmp_path):
        tester = SandboxTester()
        empty_dir = tmp_path / "no_test_repo"
        empty_dir.mkdir()
        res = tester.run_tests(empty_dir)
        assert res.status == "NO_TESTS"
        assert res.total_tests == 0
        assert "No tests" in res.summary

    def test_run_tests_timeout_handling(self, sandbox_env, monkeypatch):
        # Create a test that sleeps to trigger timeout
        test_file = sandbox_env / "tests" / "test_calculator.py"
        test_file.write_text("import time\ndef test_slow(): time.sleep(5)\n", encoding="utf-8")

        tester = SandboxTester(timeout_seconds=1)
        res = tester.run_tests(sandbox_env)
        assert res.status == "TIMEOUT"
        assert "timed out" in res.summary.lower()
