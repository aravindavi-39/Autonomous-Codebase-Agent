"""Tests for repository path validation."""

import pytest
from pathlib import Path

from ingestion.validator import validate_repository_path, is_path_within, ValidationError


class TestValidateRepositoryPath:
    """Test the validate_repository_path function."""

    def test_valid_directory(self, sample_repo_path: Path) -> None:
        """A valid directory should return a resolved Path."""
        result = validate_repository_path(str(sample_repo_path))
        assert result.is_dir()
        assert result.is_absolute()

    def test_nonexistent_path(self) -> None:
        """A nonexistent path should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid path"):
            validate_repository_path("/nonexistent/path/to/nothing")

    def test_file_path(self, tmp_path: Path) -> None:
        """A file (not a directory) should raise ValidationError."""
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(ValidationError, match="not a directory"):
            validate_repository_path(str(f))

    def test_empty_string(self) -> None:
        """An empty string path should raise ValidationError."""
        with pytest.raises(ValidationError):
            validate_repository_path("")


class TestIsPathWithin:
    """Test the is_path_within helper."""

    def test_child_within_parent(self, tmp_path: Path) -> None:
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)
        assert is_path_within(child, tmp_path) is True

    def test_parent_not_within_child(self, tmp_path: Path) -> None:
        child = tmp_path / "sub"
        child.mkdir()
        assert is_path_within(tmp_path, child) is False

    def test_same_path(self, tmp_path: Path) -> None:
        assert is_path_within(tmp_path, tmp_path) is True

    def test_traversal_attempt(self, tmp_path: Path) -> None:
        """A traversal path (e.g. using ..) resolved outside parent is caught."""
        outside = tmp_path / ".." / ".." / "etc"
        assert is_path_within(outside, tmp_path) is False
