"""Reusable UI components, badges, formatters, and banners for the Streamlit Web UI.

Preserves backward compatibility with Phase 8.1 helper functions while providing
standardized presentation elements for all pages.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

from analysis.findings.models import Severity
from refactoring.models import SafetyClassification
import web.state as state


# ---------------------------------------------------------------------------
# Color Mappings & Badges
# ---------------------------------------------------------------------------
def get_severity_badge_color(severity: Severity | str) -> str:
    """Return badge color hex code for finding severity."""
    val = severity.value if isinstance(severity, Severity) else str(severity).upper()
    colors = {
        "CRITICAL": "#d32f2f",
        "HIGH": "#f57c00",
        "MEDIUM": "#fbc02d",
        "LOW": "#0288d1",
        "INFO": "#757575",
    }
    return colors.get(val, "#757575")


def get_safety_badge_color(safety: SafetyClassification | str) -> str:
    """Return badge color hex code for refactoring safety tier."""
    val = safety.value if isinstance(safety, SafetyClassification) else str(safety)
    colors = {
        "SAFE_AUTOMATIC_PROPOSAL": "#2e7d32",
        "REVIEW_REQUIRED": "#ed6c02",
        "UNSUPPORTED": "#d32f2f",
    }
    return colors.get(val, "#757575")


def get_safety_color(classification_str: str) -> str:
    """Return color name or hex for safety tier string."""
    colors = {
        "SAFE_AUTOMATIC_PROPOSAL": "green",
        "REVIEW_REQUIRED": "orange",
        "UNSUPPORTED": "red",
        "UNKNOWN": "gray",
    }
    return colors.get(classification_str, "gray")


def render_severity_badge_html(severity: Severity | str) -> str:
    """Render an inline HTML span with colored severity badge."""
    val = severity.value if isinstance(severity, Severity) else str(severity).upper()
    color = get_severity_badge_color(val)
    return f"<span style='background-color:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold'>{val}</span>"


def render_safety_badge_html(safety: SafetyClassification | str) -> str:
    """Render an inline HTML span with colored safety badge."""
    val = safety.value if isinstance(safety, SafetyClassification) else str(safety)
    color = get_safety_badge_color(val)
    return f"<span style='background-color:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold'>{val}</span>"


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------
def format_citation_markdown(citation: Any) -> str:
    """Format a verified citation into clean markdown representation."""
    if hasattr(citation, "format_citation"):
        return citation.format_citation(show_entity=True)
    file_val = getattr(citation, "file", None) or getattr(citation, "file_path", "unknown")
    start = getattr(citation, "start_line", 1)
    end = getattr(citation, "end_line", start)
    entity_val = getattr(citation, "entity", None)
    entity_part = f" ({entity_val})" if entity_val else ""
    return f"📄 `{file_val}:{start}-{end}`{entity_part}"


def format_file_size(size_bytes: int) -> str:
    """Format byte size into human-readable B, KB, or MB string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# Standard UI Banners & Cards
# ---------------------------------------------------------------------------
def render_safety_banner() -> None:
    """Render the standard top-level safety invariant banner."""
    if st is None:
        return
    st.info(
        "🔒 **Safety Invariant Active:** Original target repositories are strictly read-only. "
        "All code refactorings require explicit approval and execute exclusively inside isolated temporary sandboxes.",
        icon="ℹ️",
    )


def render_not_loaded_warning(feature_name: str = "this section") -> None:
    """Render a warning prompt when no repository has been loaded."""
    if st is None:
        return
    st.warning(
        f"👈 Please select a repository in the sidebar and click **Load & Analyze** to access {feature_name}."
    )


def render_sha256_status() -> None:
    """Render current repository SHA-256 fingerprint card in sidebar or page."""
    if st is None:
        return
    fingerprint = state.get_initial_sha256()
    if fingerprint:
        st.success("Target Repo: Fingerprinted")
        st.caption(f"SHA-256: `{fingerprint[:16]}...`")
    else:
        st.info("Target Repo: Not Loaded")
