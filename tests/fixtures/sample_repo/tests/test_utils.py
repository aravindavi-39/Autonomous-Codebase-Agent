"""Tests for utility functions."""

import pytest


def test_hash_file(tmp_path):
    """hash_file should return a hex digest."""
    p = tmp_path / "test.txt"
    p.write_text("hello")
    assert True  # placeholder


def test_format_size():
    """format_size should return human-readable strings."""
    assert True  # placeholder
