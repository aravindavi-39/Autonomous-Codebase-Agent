"""Dashboard overview page for the Autonomous Codebase Agent Web UI."""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

import web.components as components
import web.state as state


def render() -> None:
    """Render the project-wide dashboard overview."""
    if st is None:
        return

    st.header("📊 Dashboard & Health Overview")
    st.caption("Comprehensive overview of repository structure, analysis pipeline state, and refactoring readiness.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("the Dashboard")
        st.markdown(
            """
            ### Welcome to Autonomous Codebase Understanding & Refactor Agent
            
            This agent performs deterministic static analysis, grounded architectural Q&A, and 
            isolated sandbox refactorings with multi-layer verification.
            
            **To get started:**
            1. Select a repository preset or enter a local path in the sidebar.
            2. Click **🚀 Load & Analyze** to trigger the analysis pipeline.
            3. Explore the results through the navigation menu.
            """
        )
        return

    manifest = state.get_manifest()
    code_index = state.get_code_index()
    code_graph = state.get_code_graph()
    report = state.get_analysis_report()
    plan = state.get_refactoring_plan()
    repo_path = state.get_repo_path()
    sha256 = state.get_initial_sha256()

    if not manifest:
        return

    # Top Repository Card
    st.markdown(
        f"""
        <div style="background-color:#f0f2f6;padding:16px;border-radius:8px;margin-bottom:16px">
            <h4 style="margin:0 0 8px 0;">📦 {manifest.name}</h4>
            <div><b>Path:</b> <code>{repo_path}</code></div>
            <div><b>Fingerprint (SHA-256):</b> <code>{sha256 if sha256 else 'Not fingerprinted'}</code></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Key Metrics Row
    stats = manifest.statistics
    total_classes = len(code_index.get_classes()) if code_index else 0
    total_functions = len(code_index.get_functions()) if code_index else 0
    total_findings = len(report.findings) if report else 0
    total_proposals = len(plan.actions) if plan else 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Files", f"{stats.total_files:,}")
    col2.metric("Lines of Code", f"{stats.total_lines:,}")
    col3.metric("Classes", total_classes)
    col4.metric("Functions", total_functions)
    col5.metric("Findings", total_findings)
    col6.metric("Proposals", total_proposals)

    st.divider()

    # Pipeline Phase Status
    st.subheader("⚡ Pipeline Phase Status")
    pcol1, pcol2, pcol3, pcol4 = st.columns(4)

    with pcol1:
        st.markdown("**Phase 1: Ingestion**")
        st.success(f"✅ Ingested ({stats.total_files} files)")

    with pcol2:
        st.markdown("**Phase 2: AST Analysis**")
        if code_index:
            st.success(f"✅ Indexed ({total_classes} classes)")
        else:
            st.info("Pending")

    with pcol3:
        st.markdown("**Phase 3: CodeGraph**")
        if code_graph:
            node_count = len(code_graph.nodes)
            edge_count = len(code_graph.edges)
            st.success(f"✅ Built ({node_count} nodes, {edge_count} edges)")
        else:
            st.info("Pending")

    with pcol4:
        st.markdown("**Phase 5: Findings**")
        if report:
            st.success(f"✅ Analyzed ({total_findings} issues)")
        else:
            st.info("Pending")

    pcol5, pcol6, pcol7, pcol8 = st.columns(4)
    with pcol5:
        st.markdown("**Phase 6: Refactoring**")
        if plan:
            st.success(f"✅ Planned ({total_proposals} proposals)")
        else:
            st.info("Pending")

    with pcol6:
        st.markdown("**Phase 7: Sandbox Apply**")
        sb_session = state.get_sandbox_result()
        if sb_session:
            st.success(f"✅ Session `{sb_session.id[:8]}` ({sb_session.status.value})")
        else:
            st.info("Awaiting user approval")

    with pcol7:
        st.markdown("**Phase 8: Verification**")
        verif_rep = state.get_verification_report()
        if verif_rep:
            st.success(f"✅ Audited ({verif_rep.verdict.value})")
        else:
            st.info("Not run")

    with pcol8:
        st.markdown("**Safety Status**")
        st.success("🔒 Read-Only Active")

    st.divider()

    # Quick overview split
    qcol1, qcol2 = st.columns(2)
    with qcol1:
        st.markdown("### 🌐 Language Breakdown")
        if stats.files_by_language:
            lang_data = [{"Language": lang, "Files": count} for lang, count in stats.files_by_language.items()]
            st.dataframe(lang_data, use_container_width=True, hide_index=True)
        else:
            st.info("No supported languages detected.")

    with qcol2:
        st.markdown("### 🔍 Findings by Severity")
        if report and report.findings:
            sev_counts: dict[str, int] = {}
            for f in report.findings:
                sev_counts[f.severity.value] = sev_counts.get(f.severity.value, 0) + 1
            sev_data = [{"Severity": sev, "Count": cnt} for sev, cnt in sev_counts.items()]
            st.dataframe(sev_data, use_container_width=True, hide_index=True)
        else:
            st.info("No findings reported.")
