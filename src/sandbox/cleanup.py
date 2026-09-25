"""SandboxCleanup: safely removes temporary sandbox directories with path guardrails."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import tempfile
import time

from utils.logger import setup_logger

logger = setup_logger(__name__)


def _handle_remove_readonly(func, path, exc_info):
    """Error handler for shutil.rmtree on Windows when files are read-only."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


class SandboxCleanup:
    """Safely cleans up temporary directories created for sandbox sessions."""

    def cleanup(self, sandbox_path: Path) -> bool:
        """Safely delete the sandbox directory with strict guardrail checks.

        Args:
            sandbox_path: The sandbox directory path to remove.

        Returns:
            True if removed successfully, False otherwise.
        """
        try:
            resolved_sandbox = sandbox_path.resolve()
        except Exception:
            return False

        if not resolved_sandbox.exists():
            return True

        # Guardrail 1: Sandbox must be inside the system temp directory
        temp_dir = Path(tempfile.gettempdir()).resolve()
        try:
            if not resolved_sandbox.is_relative_to(temp_dir):
                logger.error("Refusing to delete path outside temp directory: %s", resolved_sandbox)
                return False
        except AttributeError:
            if not str(resolved_sandbox).startswith(str(temp_dir)):
                logger.error("Refusing to delete path outside temp directory: %s", resolved_sandbox)
                return False

        # Guardrail 2: Must contain codebase_agent_sandbox_ namespace
        if "codebase_agent_sandbox_" not in str(resolved_sandbox):
            logger.error("Refusing to delete path without sandbox namespace: %s", resolved_sandbox)
            return False

        # Find the parent sandbox session root (e.g. .../codebase_agent_sandbox_<id>)
        target_to_remove = resolved_sandbox
        while target_to_remove.name and not target_to_remove.name.startswith("codebase_agent_sandbox_"):
            target_to_remove = target_to_remove.parent

        logger.info("Cleaning up sandbox directory: %s", target_to_remove)

        # Retry logic for Windows transient file locks
        for attempt in range(3):
            try:
                shutil.rmtree(target_to_remove, onerror=_handle_remove_readonly)
                if not target_to_remove.exists():
                    return True
            except Exception as exc:
                logger.warning("Attempt %d failed to remove sandbox: %s", attempt + 1, exc)
                time.sleep(0.1)

        return not target_to_remove.exists()
