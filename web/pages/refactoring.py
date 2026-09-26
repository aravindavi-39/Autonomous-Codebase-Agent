"""Refactoring plan and unified diff preview page for the Web UI."""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

from refactoring.generator import DiffGenerator
from refactoring.models import SafetyClassification
import web.components as components
import web.state as state


def render() -> None:
    """Render proposed refactoring plans, safety classifications, and unified diff previews."""
    if st is None:
        return

    st.header("🛠️ Refactoring Plans & Unified Diff Previews")
    st.caption("Inspect actionable refactoring proposals and syntax-validated unified diffs categorized by safety tier.")

    if not state.is_repo_loaded():
        components.render_not_loaded_warning("Refactoring Plans & Diffs")
        return

    plan = state.get_refactoring_plan()
    context = state.get_analysis_context()

    if not plan:
        st.info("Refactoring plan is not available. Please re-run Load & Analyze.")
        return

    actions = plan.actions
    summary = plan.summary if isinstance(plan.summary, dict) else {}
    safe_auto = summary.get("safe_automatic", getattr(plan.summary, "safe_automatic", 0))
    review_req = summary.get("review_required", getattr(plan.summary, "review_required", 0))
    unsupported = summary.get("unsupported", getattr(plan.summary, "unsupported", 0))

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("Total Proposals", len(actions))
    col_s2.metric("Safe Automatic", safe_auto)
    col_s3.metric("Review Required", review_req)
    col_s4.metric("Unsupported", unsupported)

    st.divider()

    if not actions:
        st.info("No refactoring proposals available for this codebase.")
        return

    # Filter
    safe_only = st.checkbox("Show Safe Automatic Proposals Only (SAFE_AUTOMATIC_PROPOSAL)", value=False)
    filtered_actions = actions
    if safe_only:
        filtered_actions = [
            a for a in filtered_actions
            if a.proposal.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
        ]

    st.write(f"Showing **{len(filtered_actions)}** of **{len(actions)}** refactoring actions:")

    diff_gen = DiffGenerator()
    combined_diffs: list[str] = []

    for idx, action in enumerate(filtered_actions, 1):
        proposal = action.proposal
        safety_badge = components.render_safety_badge_html(proposal.safety)

        with st.expander(
            f"Action #{idx}: {proposal.strategy} on {proposal.source_file} ({proposal.safety.value})",
            expanded=(idx == 1),
        ):
            st.markdown(
                f"**Safety Classification:** {safety_badge} | "
                f"**Target Finding:** `{proposal.finding_id}`",
                unsafe_allow_html=True,
            )
            st.write(f"**Strategy:** `{proposal.strategy}`")
            st.write(f"**Target File:** `{proposal.source_file}` (Lines {proposal.source_start_line}–{proposal.source_end_line})")
            st.write(f"**Description:** {proposal.description}")
            st.write(f"**Rationale:** {proposal.rationale}")

            # Generate Unified Diff
            diff_text = ""
            if context:
                try:
                    diff_results = diff_gen.generate(proposal=proposal, context=context)
                    diff_text = "\n".join(d.diff_text for d in diff_results if d.diff_text)
                except Exception as diff_exc:
                    st.warning(f"Could not generate diff: {diff_exc}")

            if diff_text:
                combined_diffs.append(diff_text)
                st.markdown("**Unified Diff Preview:**")
                st.code(diff_text, language="diff")

                st.download_button(
                    label=f"📥 Download Diff #{idx} (.patch)",
                    data=diff_text,
                    file_name=f"refactor_{proposal.finding_id}.patch",
                    mime="text/x-diff",
                    key=f"dl_diff_{idx}",
                )
            else:
                st.info("No unified diff available for this proposal.")

    if combined_diffs:
        st.divider()
        all_diffs_content = "\n\n".join(combined_diffs)
        st.download_button(
            label="📥 Download All Unified Diffs (.patch)",
            data=all_diffs_content,
            file_name="all_refactorings.patch",
            mime="text/x-diff",
            key="dl_all_diffs",
        )
