"""Safe text-file reading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)

DEFAULT_MAX_READ_SIZE: int = 500 * 1024  # 500 KB


def count_lines(file_path: Path) -> int:
    """Count the number of lines in a text file.

    Returns 0 if the file cannot be read.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except (OSError, PermissionError):
        return 0


def read_file_text(
    file_path: Path,
    max_size: int = DEFAULT_MAX_READ_SIZE,
    encoding: str = "utf-8",
) -> Optional[str]:
    """Read the full text content of a file.

    Returns ``None`` if the file is too large or unreadable.
    """
    try:
        size = file_path.stat().st_size
        if size > max_size:
            logger.warning(
                "File too large to read (%d bytes): %s", size, file_path
            )
            return None
        with open(file_path, "r", encoding=encoding, errors="replace") as fh:
            return fh.read()
    except (OSError, PermissionError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read file %s: %s", file_path, exc)
        return None
