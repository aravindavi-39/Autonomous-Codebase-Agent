"""Static analysis findings, code smells, and security vulnerability page for the Web UI."""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

import web.components as components
import web.state as state


def render() -> None:
    """Render static code analysis findings, security issues, and smells."""
    if st is None:
        return

    st.header("🔍 Codebase Findings & Static Analysis")
    st.caption("Inspect detected security vulnerabilities, architectural code smells, and anti-patterns.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("Findings & Static Analysis")
        return

    report = state.get_analysis_report()
    if not report:
        st.info("Analysis report is not available. Please re-run Load & Analyze.")
        return

    findings = report.findings

    # Metric counts by category
    sec_count = sum(1 for f in findings if f.category.value == "SECURITY")
    smell_count = sum(1 for f in findings if f.category.value == "CODE_SMELL")
    pattern_count = sum(1 for f in findings if f.category.value == "PATTERN")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Findings", len(findings))
    m2.metric("Security Issues", sec_count)
    m3.metric("Code Smells", smell_count)
    m4.metric("Pattern Flaws", pattern_count)

    st.divider()

    # Filters
    col_cat, col_sev, col_srch = st.columns([1, 1, 2])
    selected_cat = col_cat.selectbox(
        "Filter by Category:",
        options=["ALL", "SECURITY", "CODE_SMELL", "PATTERN"],
        index=0,
    )
    selected_sev = col_sev.selectbox(
        "Filter by Severity:",
        options=["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
        index=0,
    )
    search_term = col_srch.text_input("Filter by title or entity:", value="")

    filtered_findings = findings
    if selected_cat != "ALL":
        filtered_findings = [f for f in filtered_findings if f.category.value == selected_cat]
    if selected_sev != "ALL":
        filtered_findings = [f for f in filtered_findings if f.severity.value == selected_sev]
    if search_term.strip():
        term = search_term.lower()
        filtered_findings = [
            f for f in filtered_findings
            if term in f.title.lower() or (f.entity and term in f.entity.lower()) or term in f.file.lower()
        ]

    st.write(f"Showing **{len(filtered_findings)}** of **{len(findings)}** findings:")

    if not filtered_findings:
        st.success("✅ No findings match the selected filters.")
        return

    # Render finding cards
    for idx, finding in enumerate(filtered_findings, 1):
        sev_color = components.get_severity_badge_color(finding.severity)
        sev_badge = components.render_severity_badge_html(finding.severity)
        
        with st.expander(
            f"#{idx} [{finding.severity.value}] {finding.title} — {finding.file}:{finding.start_line}",
            expanded=(idx == 1),
        ):
            st.markdown(
                f"**Finding ID:** `{finding.id}` | "
                f"**Category:** `{finding.category.value}` | "
                f"**Severity:** {sev_badge} | "
                f"**Confidence:** `{finding.confidence.value}`",
                unsafe_allow_html=True,
            )
            st.write(f"**Entity:** `{finding.entity or 'N/A'}` in `{finding.file}:{finding.start_line}-{finding.end_line}`")
            st.markdown(f"**Description:** {finding.description}")

            if finding.evidence:
                st.markdown("**Evidence Code:**")
                st.code(finding.evidence, language="python")

            st.markdown(f"**Why it matters:** {finding.rationale}")
            st.info(f"💡 **Recommendation:** {finding.recommendation}")

    st.divider()
    # Download JSON button
    json_data = report.to_json(indent=2)
    st.download_button(
        label="📥 Download Findings Report (JSON)",
        data=json_data,
        file_name="findings_report.json",
        mime="application/json",
    )
