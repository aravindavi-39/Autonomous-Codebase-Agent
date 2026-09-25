"""File and directory discovery with safety filtering."""

from __future__ import annotations

import os
from pathlib import Path

from ingestion.classifier import classify_file
from ingestion.languages import detect_language
from ingestion.models import DirectoryInfo, FileMetadata, FileRecord
from ingestion.reader import count_lines
from ingestion.validator import is_path_within
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ── Directories to skip ──────────────────────────────────────────────────
IGNORED_DIRECTORIES: set[str] = {
    ".git", ".svn", ".hg",
    ".venv", "venv", "env",
    "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", ".nox",
    "dist", "build", "coverage", "htmlcov",
    ".idea", ".vscode",
    ".eggs",
}

# ── Secret / sensitive file detection ────────────────────────────────────
_SECRET_EXACT: set[str] = {
    ".env", ".env.local", ".env.development", ".env.production",
    ".env.staging", ".env.test",
}
_SECRET_SUBSTRINGS: list[str] = [
    "secret", "password", "credential", "private_key", "api_key",
]
_SECRET_EXTENSIONS: set[str] = {".pem", ".key", ".crt", ".pfx", ".p12"}

# ── Binary extensions ────────────────────────────────────────────────────
BINARY_EXTENSIONS: set[str] = {
    # Executables / libraries
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".lib",
    # JVM
    ".class", ".jar", ".war", ".ear",
    # Python bytecode
    ".pyc", ".pyo", ".pyd", ".whl",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".tiff", ".tif", ".svg",
    # Audio / Video
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".ogg", ".mkv",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Database
    ".db", ".sqlite", ".sqlite3", ".mdb",
    # Misc
    ".bin", ".dat", ".iso", ".img",
}

DEFAULT_MAX_FILE_SIZE: int = 500 * 1024  # 500 KB


# ── helpers ──────────────────────────────────────────────────────────────

def _is_ignored_directory(name: str) -> bool:
    return name in IGNORED_DIRECTORIES or name.endswith(".egg-info")


def _is_secret_file(file_name: str, extension: str) -> bool:
    low = file_name.lower()
    if low in _SECRET_EXACT or low.startswith(".env"):
        return True
    if extension.lower() in _SECRET_EXTENSIONS:
        return True
    for sub in _SECRET_SUBSTRINGS:
        if sub in low:
            return True
    if low.startswith("id_rsa") or low.startswith("id_ed25519") or low.startswith("id_dsa"):
        return True
    return False


def _is_binary_content(file_path: Path, sample_size: int = 8192) -> bool:
    """Heuristic: check for null bytes in the first *sample_size* bytes."""
    try:
        with open(file_path, "rb") as fh:
            chunk = fh.read(sample_size)
        return b"\x00" in chunk
    except (OSError, PermissionError):
        return True


# ── public API ───────────────────────────────────────────────────────────

def discover_files(
    root: Path,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> tuple[list[FileRecord], list[DirectoryInfo]]:
    """Walk *root* and return ``(file_records, directory_infos)``.

    Applies all ignore / safety filters.
    """
    files: list[FileRecord] = []
    directories: list[DirectoryInfo] = []
    root = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)

        if not is_path_within(current, root):
            logger.warning("Skipping path outside repo root: %s", current)
            dirnames.clear()
            continue

        # Prune ignored directories (in-place so os.walk skips them)
        dirnames[:] = sorted(d for d in dirnames if not _is_ignored_directory(d))

        # Record directory (skip the root itself)
        rel_dir = current.relative_to(root)
        if rel_dir != Path("."):
            directories.append(
                DirectoryInfo(
                    relative_path=rel_dir.as_posix(),
                    name=current.name,
                    file_count=len(filenames),
                    subdirectory_count=len(dirnames),
                )
            )

        for fname in sorted(filenames):
            file_path = current / fname
            rel_path = file_path.relative_to(root).as_posix()
            extension = file_path.suffix

            if _is_secret_file(fname, extension):
                logger.debug("Skipping secret file: %s", rel_path)
                continue

            if extension.lower() in BINARY_EXTENSIONS:
                logger.debug("Skipping binary file: %s", rel_path)
                continue

            try:
                size = file_path.stat().st_size
            except OSError:
                logger.warning("Cannot stat file: %s", rel_path)
                continue

            if size > max_file_size:
                logger.debug("Skipping large file (%d B): %s", size, rel_path)
                continue

            if size > 0 and _is_binary_content(file_path):
                logger.debug("Skipping binary content: %s", rel_path)
                continue

            language = detect_language(fname, extension)
            line_count = count_lines(file_path)
            is_doc, is_config, is_test = classify_file(fname, extension, rel_path)

            files.append(
                FileRecord(
                    relative_path=rel_path,
                    file_name=fname,
                    extension=extension,
                    language=language,
                    metadata=FileMetadata(
                        size_bytes=size,
                        line_count=line_count,
                        is_binary=False,
                    ),
                    is_documentation=is_doc,
                    is_configuration=is_config,
                    is_test_file=is_test,
                )
            )

    logger.info("Discovered %d files in %d directories", len(files), len(directories))
    return files, directories
