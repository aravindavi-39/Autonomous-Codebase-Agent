"""Tests for safe text file reading."""

from pathlib import Path

import pytest

from ingestion.reader import count_lines, read_file_text


class TestCountLines:
    """Test the count_lines function."""

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert count_lines(f) == 0

    def test_single_line(self, tmp_path: Path) -> None:
        f = tmp_path / "one.txt"
        f.write_text("hello\n")
        assert count_lines(f) == 1

    def test_multiple_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.txt"
        f.write_text("a\nb\nc\nd\n")
        assert count_lines(f) == 4

    def test_no_trailing_newline(self, tmp_path: Path) -> None:
        f = tmp_path / "no_nl.txt"
        f.write_text("a\nb\nc")
        assert count_lines(f) == 3

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.txt"
        assert count_lines(f) == 0


class TestReadFileText:
    """Test the read_file_text function."""

    def test_read_normal_file(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello world")
        result = read_file_text(f)
        assert result == "hello world"

    def test_read_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "utf8.txt"
        f.write_text("café ñ 日本語", encoding="utf-8")
        result = read_file_text(f)
        assert "café" in result

    def test_file_too_large(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("x" * 1000)
        result = read_file_text(f, max_size=500)
        assert result is None

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.txt"
        result = read_file_text(f)
        assert result is None

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = read_file_text(f)
        assert result == ""
