"""SandboxCopier: safely copies repository contents to an isolated sandbox."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Set

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Standard directory/file names to exclude when copying to sandbox
EXCLUDE_DIRS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".coverage",
    "node_modules",
    ".idea",
    ".vscode",
    ".tox",
}


def compute_directory_fingerprint(directory: Path) -> str:
    """Calculate deterministic SHA-256 hash across all tracked source files in directory."""
    hasher = hashlib.sha256()
    resolved_dir = directory.resolve()

    for path in sorted(resolved_dir.rglob("*")):
        # Skip excluded directory paths
        rel_parts = path.relative_to(resolved_dir).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue

        if path.is_file() and not path.is_symlink():
            rel_str = str(path.relative_to(resolved_dir)).replace("\\", "/")
            hasher.update(rel_str.encode("utf-8"))
            try:
                hasher.update(path.read_bytes())
            except Exception as exc:
                logger.warning("Failed to read file %s for fingerprint: %s", path, exc)

    return hasher.hexdigest()


class SandboxCopier:
    """Creates a physically isolated copy of a repository for sandboxed patching and testing."""

    def __init__(self, temp_base_dir: Path | None = None) -> None:
        self.temp_base_dir = temp_base_dir or Path(tempfile.gettempdir())

    def create_sandbox(self, source_path: Path, session_id: str) -> Path:
        """Create an isolated copy of source_path in a dedicated temporary sandbox directory.

        Args:
            source_path: The local repository directory.
            session_id: Unique session ID to namespace the sandbox.

        Returns:
            The Path to the newly created isolated repository root inside the sandbox.
        """
        resolved_source = source_path.resolve()
        if not resolved_source.exists() or not resolved_source.is_dir():
            raise ValueError(f"Source repository path does not exist or is not a directory: {source_path}")

        # Destination base directory
        sandbox_base = self.temp_base_dir / f"codebase_agent_sandbox_{session_id}"
        sandbox_repo_dir = sandbox_base / resolved_source.name

        # Prevent sandbox path escaping or collision
        if sandbox_repo_dir.exists():
            shutil.rmtree(sandbox_repo_dir, ignore_errors=True)

        sandbox_repo_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Creating sandbox copy for %s at %s",
            resolved_source,
            sandbox_repo_dir,
        )

        for root, dirs, files in os.walk(resolved_source, followlinks=False):
            current_root = Path(root)
            rel_root = current_root.relative_to(resolved_source)

            # Filter out excluded directories in-place so os.walk does not descend
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            dest_root = sandbox_repo_dir / rel_root
            dest_root.mkdir(parents=True, exist_ok=True)

            for file_name in files:
                src_file = current_root / file_name
                dest_file = dest_root / file_name

                # Symlink safety check: do not follow or copy external symlinks
                if src_file.is_symlink():
                    try:
                        resolved_target = src_file.resolve()
                        if not resolved_target.is_relative_to(resolved_source):
                            logger.warning(
                                "Skipping symlink %s pointing outside repository root: %s",
                                src_file,
                                resolved_target,
                            )
                            continue
                    except Exception:
                        continue

                # Copy file data and metadata
                try:
                    shutil.copy2(src_file, dest_file)
                except Exception as exc:
                    logger.warning("Failed to copy %s to sandbox: %s", src_file, exc)

        return sandbox_repo_dir
