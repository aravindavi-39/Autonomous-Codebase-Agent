"""Tests for reusable Web UI presentation components, badges, and formatters."""

from __future__ import annotations

import pytest

from analysis.findings.models import Severity
from citations.models import Citation
from refactoring.models import SafetyClassification
import web.components as components
import web.state as state


def test_severity_badge_colors():
    """Verify severity color lookup for all enum members and string variants."""
    for sev in Severity:
        color = components.get_severity_badge_color(sev)
        assert color.startswith("#")
        assert len(color) == 7

    assert components.get_severity_badge_color("CRITICAL") == "#d32f2f"
    assert components.get_severity_badge_color("unknown") == "#757575"


def test_safety_badge_colors():
    """Verify safety tier color lookup for all enum members and string variants."""
    for safety in SafetyClassification:
        color = components.get_safety_badge_color(safety)
        assert color.startswith("#")
        assert len(color) == 7

    assert components.get_safety_badge_color(SafetyClassification.SAFE_AUTOMATIC_PROPOSAL) == "#2e7d32"
    assert components.get_safety_badge_color("UNSUPPORTED") == "#d32f2f"


def test_safety_color_strings():
    """Verify string color names for safety classifications."""
    assert components.get_safety_color("SAFE_AUTOMATIC_PROPOSAL") == "green"
    assert components.get_safety_color("REVIEW_REQUIRED") == "orange"
    assert components.get_safety_color("UNSUPPORTED") == "red"
    assert components.get_safety_color("OTHER") == "gray"


def test_badge_html_rendering():
    """Verify HTML span badge generation."""
    sev_html = components.render_severity_badge_html(Severity.CRITICAL)
    assert "<span" in sev_html
    assert "CRITICAL" in sev_html
    assert "#d32f2f" in sev_html

    safe_html = components.render_safety_badge_html(SafetyClassification.SAFE_AUTOMATIC_PROPOSAL)
    assert "<span" in safe_html
    assert "SAFE_AUTOMATIC_PROPOSAL" in safe_html
    assert "#2e7d32" in safe_html


def test_format_file_size():
    """Verify human-readable file size formatting."""
    assert components.format_file_size(100) == "100 B"
    assert components.format_file_size(1024) == "1.0 KB"
    assert components.format_file_size(2560) == "2.5 KB"
    assert components.format_file_size(1048576) == "1.0 MB"
    assert components.format_file_size(5242880) == "5.0 MB"


def test_format_citation_markdown():
    """Verify citation markdown generation."""
    cit_with = Citation(
        file="src/calc.py",
        start_line=10,
        end_line=20,
        entity="multiply",
        snippet="def multiply(a, b): return a * b",
    )
    res_with = components.format_citation_markdown(cit_with)
    assert "src/calc.py:10-20" in res_with
    assert "(multiply)" in res_with

    cit_without = Citation(
        file="src/calc.py",
        start_line=1,
        end_line=5,
        entity=None,
    )
    res_without = components.format_citation_markdown(cit_without)
    assert "src/calc.py:1-5" in res_without
    assert "(" not in res_without


def test_render_safety_banner_executes():
    """Verify render_safety_banner runs without error."""
    components.render_safety_banner()


def test_render_not_loaded_warning_executes():
    """Verify render_not_loaded_warning runs without error."""
    components.render_not_loaded_warning("Test Feature")


def test_render_sha256_status_executes():
    """Verify render_sha256_status runs without error with and without fingerprint."""
    state.reset_session_cache()
    components.render_sha256_status()

    state.set_initial_sha256("1234567890abcdef")
    components.render_sha256_status()
    state.reset_session_cache()
