"""Tests for repository statistics calculation."""

from pathlib import Path

import pytest

from ingestion.discoverer import discover_files
from ingestion.models import Language, FileMetadata, FileRecord
from ingestion.statistics import calculate_statistics


def _make_record(
    name: str,
    ext: str,
    lang: Language,
    size: int = 100,
    lines: int = 10,
    is_doc: bool = False,
    is_config: bool = False,
    is_test: bool = False,
) -> FileRecord:
    """Helper to build a FileRecord quickly."""
    return FileRecord(
        relative_path=name,
        file_name=name,
        extension=ext,
        language=lang,
        metadata=FileMetadata(size_bytes=size, line_count=lines),
        is_documentation=is_doc,
        is_configuration=is_config,
        is_test_file=is_test,
    )


class TestCalculateStatistics:
    """Test the calculate_statistics function."""

    def test_empty_file_list(self) -> None:
        stats = calculate_statistics([], total_directories=0)
        assert stats.total_files == 0
        assert stats.total_directories == 0
        assert stats.total_lines == 0
        assert stats.files_by_language == {}

    def test_total_counts(self) -> None:
        files = [
            _make_record("a.py", ".py", Language.PYTHON, lines=10),
            _make_record("b.py", ".py", Language.PYTHON, lines=20),
            _make_record("c.js", ".js", Language.JAVASCRIPT, lines=5),
        ]
        stats = calculate_statistics(files, total_directories=2)
        assert stats.total_files == 3
        assert stats.total_directories == 2
        assert stats.total_lines == 35

    def test_files_by_language(self) -> None:
        files = [
            _make_record("a.py", ".py", Language.PYTHON),
            _make_record("b.py", ".py", Language.PYTHON),
            _make_record("c.js", ".js", Language.JAVASCRIPT),
            _make_record("d.ts", ".ts", Language.TYPESCRIPT),
        ]
        stats = calculate_statistics(files, total_directories=0)
        assert stats.files_by_language["Python"] == 2
        assert stats.files_by_language["JavaScript"] == 1
        assert stats.files_by_language["TypeScript"] == 1

    def test_language_counts_sorted_descending(self) -> None:
        files = [
            _make_record("a.js", ".js", Language.JAVASCRIPT),
            _make_record("b.py", ".py", Language.PYTHON),
            _make_record("c.py", ".py", Language.PYTHON),
            _make_record("d.py", ".py", Language.PYTHON),
        ]
        stats = calculate_statistics(files, total_directories=0)
        keys = list(stats.files_by_language.keys())
        assert keys[0] == "Python"  # 3 > 1

    def test_largest_files(self) -> None:
        files = [
            _make_record("small.py", ".py", Language.PYTHON, size=50),
            _make_record("big.py", ".py", Language.PYTHON, size=5000),
            _make_record("med.py", ".py", Language.PYTHON, size=500),
        ]
        stats = calculate_statistics(files, total_directories=0, top_n_largest=2)
        assert len(stats.largest_files) == 2
        assert stats.largest_files[0].metadata.size_bytes == 5000
        assert stats.largest_files[1].metadata.size_bytes == 500

    def test_test_files_collected(self) -> None:
        files = [
            _make_record("app.py", ".py", Language.PYTHON, is_test=False),
            _make_record("test_app.py", ".py", Language.PYTHON, is_test=True),
            _make_record("test_utils.py", ".py", Language.PYTHON, is_test=True),
        ]
        stats = calculate_statistics(files, total_directories=0)
        assert len(stats.test_files) == 2

    def test_documentation_files_collected(self) -> None:
        files = [
            _make_record("README.md", ".md", Language.MARKDOWN, is_doc=True),
            _make_record("app.py", ".py", Language.PYTHON, is_doc=False),
        ]
        stats = calculate_statistics(files, total_directories=0)
        assert len(stats.documentation_files) == 1

    def test_configuration_files_collected(self) -> None:
        files = [
            _make_record("pyproject.toml", ".toml", Language.TOML, is_config=True),
            _make_record(".gitignore", "", Language.UNKNOWN, is_config=True),
            _make_record("app.py", ".py", Language.PYTHON, is_config=False),
        ]
        stats = calculate_statistics(files, total_directories=0)
        assert len(stats.configuration_files) == 2


class TestStatisticsFromSampleRepo:
    """Integration test: statistics from the sample repo fixture."""

    def test_sample_repo_stats(self, sample_repo_path: Path) -> None:
        files, dirs = discover_files(sample_repo_path)
        stats = calculate_statistics(files, total_directories=len(dirs))

        assert stats.total_files > 10
        assert stats.total_directories > 3
        assert stats.total_lines > 50
        assert "Python" in stats.files_by_language
        assert len(stats.test_files) >= 2
        assert len(stats.documentation_files) >= 2
        assert len(stats.configuration_files) >= 2
        assert len(stats.largest_files) > 0
