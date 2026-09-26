"""Centralized reporting and artifact export hub for the Autonomous Codebase Agent Web UI."""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

import web.components as components
import web.state as state


def render() -> None:
    """Render the reports hub and artifact export center."""
    if st is None:
        return

    st.header("📊 Reports & Artifact Export Center")
    st.caption("Inspect and download structured JSON reports and diff patches generated across all analysis and verification phases.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("the Reports Center")
        return

    manifest = state.get_manifest()
    code_index = state.get_code_index()
    code_graph = state.get_code_graph()
    analysis_report = state.get_analysis_report()
    plan = state.get_refactoring_plan()
    sb_report = state.get_sandbox_report()
    v_report = state.get_verification_report()

    # Collect available reports
    reports_map: dict[str, str] = {}

    if manifest:
        try:
            reports_map["Repository Manifest (JSON)"] = manifest.model_dump_json(indent=2)
        except Exception:
            pass

    if code_index:
        try:
            reports_map["Code Index (JSON)"] = code_index.export_json()
        except Exception:
            pass

    if code_graph:
        try:
            reports_map["CodeGraph Architecture (JSON)"] = code_graph.export_json()
        except Exception:
            pass

    if analysis_report:
        try:
            reports_map["Analysis Findings Report (JSON)"] = analysis_report.to_json(indent=2)
        except Exception:
            pass

    if plan:
        try:
            reports_map["Refactoring Plan (JSON)"] = plan.to_json(indent=2)
        except Exception:
            pass

    if sb_report:
        try:
            reports_map["Sandbox Session Report (JSON)"] = sb_report.to_json(indent=2)
        except Exception:
            pass

    if v_report:
        try:
            reports_map["Verification Audit Report (JSON)"] = v_report.to_json(indent=2)
        except Exception:
            pass

    st.subheader(f"Available Export Artifacts ({len(reports_map)})")

    # Download buttons grid
    dcols = st.columns(3)
    col_idx = 0
    for name, content in reports_map.items():
        fname = name.lower().replace(" ", "_").replace("(", "").replace(")", "") + ".json"
        with dcols[col_idx % 3]:
            st.download_button(
                label=f"📥 {name}",
                data=content,
                file_name=fname,
                mime="application/json",
                key=f"dl_rep_{col_idx}",
                use_container_width=True,
            )
        col_idx += 1

    st.divider()

    # Interactive JSON Viewer
    st.subheader("🔍 Interactive Report Preview")
    selected_report_name = st.selectbox("Select Report to Preview:", options=list(reports_map.keys()), index=0)
    if selected_report_name in reports_map:
        st.code(reports_map[selected_report_name], language="json")
