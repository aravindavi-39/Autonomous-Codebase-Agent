"""Sandbox manager — isolated working copy management and verification.

This package provides:
- Safe, isolated repository copying
- Pre/post-patch validation and atomic patch application
- Subprocess test execution inside the sandbox with environment sanitization
- Regression verification and test comparison
- Guarded sandbox cleanup and target repository immutability verification
"""

from sandbox.cleanup import SandboxCleanup
from sandbox.copier import SandboxCopier, compute_directory_fingerprint
from sandbox.manager import SandboxManager
from sandbox.models import (
    ApprovalStatus,
    PatchApplicationResult,
    RegressionStatus,
    SandboxReport,
    SandboxSession,
    SandboxStatus,
    TestComparison,
    TestRun,
    redact_secrets,
)
from sandbox.patcher import SandboxPatcher
from sandbox.tester import SandboxTester
from sandbox.verifier import RegressionVerifier

__all__ = [
    "SandboxCleanup",
    "SandboxCopier",
    "SandboxManager",
    "SandboxPatcher",
    "SandboxTester",
    "RegressionVerifier",
    "SandboxSession",
    "SandboxReport",
    "SandboxStatus",
    "ApprovalStatus",
    "RegressionStatus",
    "PatchApplicationResult",
    "TestRun",
    "TestComparison",
    "compute_directory_fingerprint",
    "redact_secrets",
]
