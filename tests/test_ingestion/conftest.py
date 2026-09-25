"""Shared fixtures for ingestion tests."""

from pathlib import Path

import pytest

# Path to the static sample repository fixture
SAMPLE_REPO_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
def sample_repo_path() -> Path:
    """Return the path to the static sample repository fixture."""
    assert SAMPLE_REPO_DIR.is_dir(), f"Fixture not found: {SAMPLE_REPO_DIR}"
    return SAMPLE_REPO_DIR


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a minimal temporary repository for edge-case tests."""
    # Create some basic files
    (tmp_path / "README.md").write_text("# Temp Repo\n", encoding="utf-8")
    (tmp_path / "main.py").write_text(
        'print("hello")\n', encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def run():\n    pass\n", encoding="utf-8"
    )
    return tmp_path
