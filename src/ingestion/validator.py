"""Repository path validation and safety checks."""

from __future__ import annotations

import os
from pathlib import Path

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ValidationError(Exception):
    """Raised when repository path validation fails."""


def validate_repository_path(path: str) -> Path:
    """Validate and resolve a repository path.

    Checks:
    - Path exists
    - Path is a directory
    - Path is readable
    - Path is not a system root directory

    Returns:
        The resolved ``Path``.

    Raises:
        ValidationError: If any check fails.
    """
    if not path or not path.strip():
        raise ValidationError("Path must not be empty.")

    try:
        resolved = Path(path).resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"Invalid path: {path!r} — {exc}") from exc

    if not resolved.exists():
        raise ValidationError(f"Path does not exist: {resolved}")

    if not resolved.is_dir():
        raise ValidationError(f"Path is not a directory: {resolved}")

    if not os.access(resolved, os.R_OK):
        raise ValidationError(f"Path is not readable: {resolved}")

    # Refuse to scan root / system directories
    if len(resolved.parts) <= 1:
        raise ValidationError(
            f"Refusing to scan a root/system directory: {resolved}"
        )

    logger.info("Repository path validated: %s", resolved)
    return resolved


def is_path_within(child: Path, parent: Path) -> bool:
    """Return True if *child* is strictly within *parent* (no traversal)."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
