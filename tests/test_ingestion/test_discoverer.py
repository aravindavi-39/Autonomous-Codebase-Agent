"""Tests for file and directory discovery with filtering."""

from pathlib import Path

import pytest

from ingestion.discoverer import (
    DEFAULT_MAX_FILE_SIZE,
    IGNORED_DIRECTORIES,
    _is_ignored_directory,
    _is_secret_file,
    discover_files,
)
from ingestion.models import Language


class TestIgnoredDirectories:
    """Verify ignored directories are filtered out."""

    @pytest.mark.parametrize(
        "dirname",
        [
            ".git", ".venv", "venv", "node_modules", "__pycache__",
            ".pytest_cache", "dist", "build", "coverage",
        ],
    )
    def test_known_ignored_dirs(self, dirname: str) -> None:
        """Each required ignored directory name must be filtered."""
        assert _is_ignored_directory(dirname) is True

    def test_egg_info_pattern(self) -> None:
        """Directories ending in .egg-info should be ignored."""
        assert _is_ignored_directory("mypackage.egg-info") is True

    def test_normal_directory_not_ignored(self) -> None:
        """A normal directory like 'src' should not be ignored."""
        assert _is_ignored_directory("src") is False

    def test_ignored_dirs_not_traversed(self, tmp_path: Path) -> None:
        """Files inside ignored directories should not appear in results."""
        # Create structure: root/src/app.py + root/node_modules/pkg/index.js
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n")
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("var x;")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "app.cpython-311.pyc").write_bytes(b"\x00")

        files, dirs = discover_files(tmp_path)
        paths = {f.relative_path for f in files}

        assert "src/app.py" in paths
        assert "node_modules/pkg/index.js" not in paths
        # __pycache__ dir itself should not appear
        dir_names = {d.name for d in dirs}
        assert "node_modules" not in dir_names
        assert "__pycache__" not in dir_names


class TestIgnoredFiles:
    """Verify secret, binary, and large files are filtered out."""

    def test_env_file_excluded(self, tmp_path: Path) -> None:
        """.env files should be excluded."""
        (tmp_path / ".env").write_text("SECRET=abc")
        (tmp_path / "app.py").write_text("x = 1")

        files, _ = discover_files(tmp_path)
        paths = {f.file_name for f in files}
        assert ".env" not in paths
        assert "app.py" in paths

    def test_env_variants_excluded(self, tmp_path: Path) -> None:
        """.env.local, .env.production etc should be excluded."""
        for name in [".env.local", ".env.production", ".env.test"]:
            (tmp_path / name).write_text("KEY=val")
        (tmp_path / "ok.txt").write_text("fine")

        files, _ = discover_files(tmp_path)
        names = {f.file_name for f in files}
        assert ".env.local" not in names
        assert ".env.production" not in names
        assert "ok.txt" in names

    def test_secret_file_patterns(self) -> None:
        """Files with secret-related names should be flagged."""
        assert _is_secret_file(".env", "") is True
        assert _is_secret_file(".env.local", ".local") is True
        assert _is_secret_file("db_password.txt", ".txt") is True
        assert _is_secret_file("api_secret.json", ".json") is True
        assert _is_secret_file("credentials.yaml", ".yaml") is True
        assert _is_secret_file("id_rsa", "") is True
        assert _is_secret_file("server.key", ".key") is True
        assert _is_secret_file("cert.pem", ".pem") is True

    def test_non_secret_files_not_excluded(self) -> None:
        """Normal files should not be flagged as secrets."""
        assert _is_secret_file("app.py", ".py") is False
        assert _is_secret_file("README.md", ".md") is False
        assert _is_secret_file(".gitignore", "") is False
        assert _is_secret_file("config.json", ".json") is False

    def test_binary_files_excluded(self, tmp_path: Path) -> None:
        """Binary files (by extension) should be excluded."""
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (tmp_path / "app.py").write_text("x = 1")

        files, _ = discover_files(tmp_path)
        names = {f.file_name for f in files}
        assert "image.png" not in names
        assert "app.py" in names

    def test_large_file_excluded(self, tmp_path: Path) -> None:
        """Files larger than max_file_size should be excluded."""
        # Create a file just over the limit
        big_file = tmp_path / "big.txt"
        big_file.write_text("x" * 1024)  # 1 KB
        small_file = tmp_path / "small.txt"
        small_file.write_text("hello")

        # Set max to 512 bytes
        files, _ = discover_files(tmp_path, max_file_size=512)
        names = {f.file_name for f in files}
        assert "big.txt" not in names
        assert "small.txt" in names

    def test_binary_content_detection(self, tmp_path: Path) -> None:
        """Files with null bytes in content should be excluded."""
        bin_file = tmp_path / "data.dat2"  # unknown extension
        bin_file.write_bytes(b"hello\x00world")
        text_file = tmp_path / "data.txt"
        text_file.write_text("hello world")

        files, _ = discover_files(tmp_path)
        names = {f.file_name for f in files}
        assert "data.dat2" not in names
        assert "data.txt" in names


class TestFileMetadata:
    """Verify correct metadata is attached to discovered files."""

    def test_file_record_fields(self, tmp_path: Path) -> None:
        """Each FileRecord should have correct basic fields."""
        (tmp_path / "main.py").write_text("x = 1\ny = 2\nz = 3\n")
        files, _ = discover_files(tmp_path)
        assert len(files) == 1
        f = files[0]
        assert f.file_name == "main.py"
        assert f.extension == ".py"
        assert f.relative_path == "main.py"
        assert f.language == Language.PYTHON
        assert f.metadata.size_bytes > 0
        assert f.metadata.line_count == 3
        assert f.metadata.is_binary is False

    def test_nested_relative_path(self, tmp_path: Path) -> None:
        """Files in subdirectories should have correct relative paths."""
        (tmp_path / "src" / "pkg").mkdir(parents=True)
        (tmp_path / "src" / "pkg" / "mod.py").write_text("pass\n")

        files, _ = discover_files(tmp_path)
        assert files[0].relative_path == "src/pkg/mod.py"


class TestLineCountingViaDiscovery:
    """Verify line counting during discovery."""

    def test_empty_file_zero_lines(self, tmp_path: Path) -> None:
        """An empty file should have 0 lines."""
        (tmp_path / "empty.py").write_text("")
        files, _ = discover_files(tmp_path)
        assert files[0].metadata.line_count == 0

    def test_single_line(self, tmp_path: Path) -> None:
        """A single-line file should have 1 line."""
        (tmp_path / "one.py").write_text("x = 1\n")
        files, _ = discover_files(tmp_path)
        assert files[0].metadata.line_count == 1

    def test_multiline(self, tmp_path: Path) -> None:
        """A multi-line file should have the correct line count."""
        (tmp_path / "multi.py").write_text("a\nb\nc\nd\ne\n")
        files, _ = discover_files(tmp_path)
        assert files[0].metadata.line_count == 5

    def test_no_trailing_newline(self, tmp_path: Path) -> None:
        """A file without a trailing newline still counts the last line."""
        (tmp_path / "no_nl.py").write_text("a\nb\nc")
        files, _ = discover_files(tmp_path)
        assert files[0].metadata.line_count == 3


class TestSampleRepoDiscovery:
    """Integration test against the sample_repo fixture."""

    def test_discovers_files(self, sample_repo_path: Path) -> None:
        """The sample repo should yield a non-empty file list."""
        files, dirs = discover_files(sample_repo_path)
        assert len(files) > 10
        assert len(dirs) > 3

    def test_no_ignored_dirs_in_results(self, sample_repo_path: Path) -> None:
        """None of the ignored directory names should appear in results."""
        files, dirs = discover_files(sample_repo_path)
        dir_names = {d.name for d in dirs}
        for ignored in ["__pycache__", "node_modules", ".git"]:
            assert ignored not in dir_names

    def test_multiple_languages(self, sample_repo_path: Path) -> None:
        """The sample repo should contain multiple programming languages."""
        files, _ = discover_files(sample_repo_path)
        languages = {f.language for f in files}
        # Should have at least Python, JS, TS, HTML, CSS
        assert Language.PYTHON in languages
        assert Language.JAVASCRIPT in languages
        assert Language.TYPESCRIPT in languages
