"""Safe sandbox execution and human approval application page for the Web UI."""

from __future__ import annotations

from pathlib import Path
try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

from refactoring.models import SafetyClassification
from sandbox.manager import SandboxManager
import web.components as components
import web.state as state


def render() -> None:
    """Render the isolated sandbox patch application view with strict approval gate."""
    if st is None:
        return

    st.header("🧪 Safe Sandbox Application & Execution")
    st.caption("Apply proposed diffs exclusively inside isolated, disposable temporary sandboxes with strict human approval.")

    # Prominent safety disclaimer
    st.warning(
        "⚠️ **Human Approval & Isolation Boundary:** The original repository is NEVER modified directly. "
        "Refactoring proposals can only be applied to temporary copies in isolated directories with explicit human confirmation.",
        icon="🛡️",
    )

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("Sandbox Application")
        return

    manifest = state.get_manifest()
    plan = state.get_refactoring_plan()
    report = state.get_analysis_report()

    if not manifest or not plan:
        st.info("Repository analysis or refactoring plan is not available.")
        return

    if not plan.actions:
        st.info("No refactoring proposals available to apply.")
        return

    st.subheader("1. Select Proposal to Apply")
    proposal_options = {
        f"{act.proposal.finding_id} — {act.proposal.strategy} ({act.proposal.safety.value})": act
        for act in plan.actions
    }
    selected_key = st.selectbox("Select Proposal:", options=list(proposal_options.keys()))
    selected_action = proposal_options[selected_key]
    selected_prop = selected_action.proposal

    is_safe = selected_prop.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
    if not is_safe:
        st.error(
            f"⛔ Cannot apply `{selected_prop.safety.value}` action to sandbox. "
            "Only `SAFE_AUTOMATIC_PROPOSAL` actions are eligible for automated sandbox application."
        )

    # Human Approval Gate Checkbox
    st.markdown("### 2. Explicit Human Approval Boundary")
    approval_checked = st.checkbox(
        "✅ I explicitly confirm and approve applying this refactoring patch to an isolated sandbox copy.",
        value=False,
        disabled=not is_safe,
        help="This action triggers patch application inside a temporary copy of the repository. The original code remains unchanged.",
    )

    col_opt1, col_opt2 = st.columns(2)
    keep_sandbox = col_opt1.checkbox("Keep sandbox directory after run (for inspection)", value=False)
    timeout_secs = col_opt2.number_input("Test execution timeout (seconds):", min_value=5, max_value=120, value=30)

    apply_btn = st.button(
        "🚀 Apply to Isolated Sandbox",
        type="primary",
        disabled=(not is_safe or not approval_checked),
        use_container_width=True,
    )

    if apply_btn:
        with st.spinner("Creating isolated sandbox, running baseline tests, applying patch, and running post-patch tests..."):
            try:
                sandbox_mgr = SandboxManager()
                sb_report = sandbox_mgr.execute_session(
                    source_path=Path(manifest.root_path),
                    proposal=selected_prop,
                    approved=True,
                    keep_sandbox=keep_sandbox,
                    timeout_seconds=int(timeout_secs),
                    audit_verification=True,
                    baseline_findings=report.findings if report else None,
                )
                state.set_sandbox_report(sb_report)
                st.success(f"Sandbox Session `{sb_report.session.id}` completed successfully!")
            except Exception as s_exc:
                st.error(f"Sandbox Application Error: {s_exc}")

    # Display Sandbox Execution Results
    session = state.get_sandbox_result()
    if session:
        st.divider()
        st.subheader("📋 Sandbox Execution Report")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Session ID", session.id)
        c2.metric("Approval Status", session.approval_status.value)
        patch_status_str = "SUCCESS" if session.patch_result and session.patch_result.success else "FAILED"
        c3.metric("Patch Status", patch_status_str)

        regression_verdict = session.test_comparison.regression_status.value if session.test_comparison else "SKIPPED"
        reg_color = "green" if regression_verdict == "PASS" else "red"
        c4.markdown(
            f"**Regression Verdict:**<br><span style='color:{reg_color};font-size:20px;font-weight:bold'>{regression_verdict}</span>",
            unsafe_allow_html=True,
        )

        base_summary = session.test_comparison.baseline_run.summary if session.test_comparison and session.test_comparison.baseline_run else "None"
        patch_summary = session.test_comparison.patched_run.summary if session.test_comparison and session.test_comparison.patched_run else "None"

        res_table = [
            {"Stage": "Baseline Tests", "Summary": base_summary},
            {"Stage": "Post-Patch Tests", "Summary": patch_summary},
            {
                "Stage": "Target Repository Immutability",
                "Summary": "UNCHANGED (Verified SHA-256 match)" if session.source_intact else "MUTATED ERROR",
            },
            {
                "Stage": "Sandbox Directory Lifecycle",
                "Summary": "CLEANED (Deleted temporary sandbox)" if session.cleaned_up else f"RETAINED at `{session.sandbox_path}`",
            },
        ]
        st.dataframe(res_table, use_container_width=True, hide_index=True)

        if session.errors:
            st.markdown("**Errors:**")
            for err in session.errors:
                st.error(err)
        if session.warnings:
            st.markdown("**Warnings:**")
            for warn in session.warnings:
                st.warning(warn)
