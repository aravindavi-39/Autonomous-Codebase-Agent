"""SandboxTester: executes test suites safely inside the isolated sandbox."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Optional

from sandbox.models import TestRun, redact_secrets
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Patterns to parse pytest test result summary lines
_PYTEST_SUMMARY_PATTERN = re.compile(
    r"=+\s*(?:(?P<passed>\d+)\s+passed)?"
    r"(?:,?\s*(?P<failed>\d+)\s+failed)?"
    r"(?:,?\s*(?P<skipped>\d+)\s+skipped)?"
    r"(?:,?\s*(?P<errors>\d+)\s+errors?)?"
    r"\s+in\s+[\d\.]+s\s*=+",
    re.IGNORECASE,
)

# Environment variables to sanitize to prevent secret leakage into test runs
SENSITIVE_ENV_VARS = {
    "OPENAI_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "SECRET_KEY",
    "PASSWORD",
    "API_KEY",
    "DATABASE_URL",
}


class SandboxTester:
    """Discovers and executes test suites inside an isolated sandbox environment."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def has_tests(self, sandbox_path: Path) -> bool:
        """Check whether sandbox repository contains test files or test configuration."""
        resolved = sandbox_path.resolve()

        # Check for tests directory
        if (resolved / "tests").is_dir() or (resolved / "test").is_dir():
            return True

        # Check for pytest configuration files
        if (resolved / "pytest.ini").is_file() or (resolved / "setup.cfg").is_file():
            return True

        # Check for any test_*.py or *_test.py files
        for f in resolved.rglob("*.py"):
            if f.name.startswith("test_") or f.name.endswith("_test.py"):
                return True

        return False

    def run_tests(
        self,
        sandbox_path: Path,
        custom_args: Optional[list[str]] = None,
    ) -> TestRun:
        """Execute the test suite inside the sandbox.

        Args:
            sandbox_path: Path to the sandbox repository root.
            custom_args: Additional pytest CLI arguments.

        Returns:
            A TestRun object detailing results.
        """
        resolved_sandbox = sandbox_path.resolve()

        if not self.has_tests(resolved_sandbox):
            logger.info("No test files or framework detected in %s", resolved_sandbox)
            return TestRun(
                framework="pytest",
                command=[],
                status="NO_TESTS",
                return_code=0,
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration_seconds=0.0,
                stdout="",
                stderr="",
                summary="No tests discovered in repository",
            )

        cmd = [sys.executable, "-m", "pytest", "-q"]
        if custom_args:
            cmd.extend(custom_args)

        # Sanitize environment variables
        env = os.environ.copy()
        for var in SENSITIVE_ENV_VARS:
            env.pop(var, None)

        # Set PYTHONPATH strictly to sandbox src and root so imports resolve inside sandbox
        sandbox_src = resolved_sandbox / "src"
        if sandbox_src.is_dir():
            env["PYTHONPATH"] = f"{sandbox_src}{os.pathsep}{resolved_sandbox}"
        else:
            env["PYTHONPATH"] = str(resolved_sandbox)

        env["PYTHONDONTWRITEBYTECODE"] = "1"

        start_time = time.time()
        try:
            process = subprocess.run(
                cmd,
                cwd=str(resolved_sandbox),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
            )
            duration = round(time.time() - start_time, 2)
            stdout = redact_secrets(process.stdout or "")
            stderr = redact_secrets(process.stderr or "")
            ret_code = process.returncode

            passed = 0
            failed = 0
            skipped = 0

            # Parse pytest summary output
            m_pass = re.search(r"(\d+)\s+passed", stdout)
            if m_pass:
                passed = int(m_pass.group(1))

            m_fail = re.search(r"(\d+)\s+failed", stdout)
            if m_fail:
                failed = int(m_fail.group(1))

            m_skip = re.search(r"(\d+)\s+skipped", stdout)
            if m_skip:
                skipped = int(m_skip.group(1))

            if "collected 0 items" in stdout or ret_code == 5:
                return TestRun(
                    framework="pytest",
                    command=cmd,
                    status="NO_TESTS",
                    return_code=ret_code,
                    total_tests=0,
                    passed=0,
                    failed=0,
                    skipped=0,
                    duration_seconds=duration,
                    stdout=stdout,
                    stderr=stderr,
                    summary="No tests collected",
                )

            total = passed + failed + skipped
            if ret_code == 0:
                status = "PASSED"
                summary = f"{passed} passed in {duration}s"
            else:
                status = "FAILED"
                summary = f"{failed} failed, {passed} passed in {duration}s"

            return TestRun(
                framework="pytest",
                command=cmd,
                status=status,
                return_code=ret_code,
                total_tests=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                duration_seconds=duration,
                stdout=stdout,
                stderr=stderr,
                summary=summary,
            )

        except subprocess.TimeoutExpired as exc:
            duration = round(time.time() - start_time, 2)
            out = redact_secrets(exc.stdout or "" if isinstance(exc.stdout, str) else "")
            err = redact_secrets(exc.stderr or "" if isinstance(exc.stderr, str) else "")
            return TestRun(
                framework="pytest",
                command=cmd,
                status="TIMEOUT",
                return_code=-1,
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration_seconds=duration,
                stdout=out,
                stderr=err,
                summary=f"Test run timed out after {self.timeout_seconds}s",
            )
        except Exception as exc:
            duration = round(time.time() - start_time, 2)
            return TestRun(
                framework="pytest",
                command=cmd,
                status="ERROR",
                return_code=-1,
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration_seconds=duration,
                stdout="",
                stderr=str(exc),
                summary=f"Failed to execute tests: {exc}",
            )
