"""Verification engine audit and multi-check resolution assessment page for the Web UI."""

from __future__ import annotations

from pathlib import Path
try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

from verification.engine import VerificationEngine
from verification.models import VerificationPolicy, VerificationVerdict
import web.components as components
import web.state as state


def render() -> None:
    """Render the multi-check verification engine audit view."""
    if st is None:
        return

    st.header("🧪 Verification Engine & Audit")
    st.caption("Perform multi-check read-only audits including subprocess test execution, AST linting, and immutability verification.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("Verification Engine")
        return

    manifest = state.get_manifest()
    if not manifest:
        return

    st.subheader("1. Configure Verification Policy & Checks")
    col_pol, col_tests, col_lint = st.columns([1, 1, 1])
    selected_policy = col_pol.selectbox("Verification Policy:", ["STRICT", "LENIENT"], index=0,
                                        help="STRICT fails on lint warnings; LENIENT tolerates warnings.")
    run_tests = col_tests.checkbox("Run Subprocess Tests", value=True)
    run_lint = col_lint.checkbox("Run AST Linter", value=True)

    target_finding_id = st.text_input("Target Finding ID (optional resolution check):", value="",
                                      placeholder="e.g. PAT-003_add_entry_6")

    verify_btn = st.button("🧪 Run Verification Audit on Repository", type="primary")

    if verify_btn:
        with st.spinner("Running full verification audit (tests, linter, findings, immutability)..."):
            try:
                policy = (
                    VerificationPolicy.strict()
                    if selected_policy == "STRICT"
                    else VerificationPolicy.lenient()
                )
                v_engine = VerificationEngine()
                v_report = v_engine.verify_repository(
                    repo_path=Path(manifest.root_path),
                    target_finding_id=target_finding_id.strip() or None,
                    policy=policy,
                    run_tests=run_tests,
                    run_lint=run_lint,
                )
                state.set_verification_report(v_report)
                st.success("Verification audit completed!")
            except Exception as v_exc:
                st.error(f"Verification Error: {v_exc}")

    # Display Verification Report
    v_report = state.get_verification_report()
    if v_report:
        st.divider()
        st.subheader("📋 Verification Report")

        v_color = "green" if v_report.verdict == VerificationVerdict.PASSED else "red"
        st.markdown(
            f"**Overall Verdict:** <span style='color:{v_color};font-size:22px;font-weight:bold'>{v_report.verdict.value}</span> "
            f"(Policy Mode: `{v_report.policy.mode.value}`)",
            unsafe_allow_html=True,
        )

        verif_rows = []
        if v_report.target_finding_id:
            delta = v_report.finding_delta
            status_str = "RESOLVED" if (delta and delta.target_resolved) else "UNRESOLVED"
            verif_rows.append({
                "Verification Check": "Target Finding Resolution",
                "Status": status_str,
                "Details": f"Target: {v_report.target_finding_id}",
            })

        if v_report.test_run:
            verif_rows.append({
                "Verification Check": "Unit Tests",
                "Status": v_report.test_run.status,
                "Details": v_report.test_run.summary,
            })
        elif v_report.test_skipped:
            verif_rows.append({
                "Verification Check": "Unit Tests",
                "Status": "SKIPPED",
                "Details": "Test execution skipped by user toggle.",
            })

        if v_report.lint_run:
            lint_status = getattr(v_report.lint_run.status, "value", str(v_report.lint_run.status))
            verif_rows.append({
                "Verification Check": "AST Lint & Syntax",
                "Status": lint_status,
                "Details": v_report.lint_run.summary,
            })
        elif v_report.lint_skipped:
            verif_rows.append({
                "Verification Check": "AST Lint & Syntax",
                "Status": "SKIPPED",
                "Details": "Linting skipped by user toggle.",
            })

        verif_rows.append({
            "Verification Check": "Target Repo Immutability",
            "Status": "UNCHANGED" if v_report.source_intact else "MUTATED ERROR",
            "Details": f"Verified SHA-256 match ({v_report.source_fingerprint_before[:16]}...)",
        })

        st.dataframe(verif_rows, use_container_width=True, hide_index=True)

        if v_report.messages:
            st.markdown("**Observations:**")
            for msg in v_report.messages:
                st.write(f"- {msg}")

        if v_report.errors:
            st.markdown("**Errors & Violations:**")
            for err in v_report.errors:
                st.error(err)

        if v_report.warnings:
            st.markdown("**Warnings:**")
            for warn in v_report.warnings:
                st.warning(warn)

        st.download_button(
            label="📥 Download Verification Report (JSON)",
            data=v_report.to_json(indent=2),
            file_name="verification_report.json",
            mime="application/json",
            key="dl_verif_rep",
        )
