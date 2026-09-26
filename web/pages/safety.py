"""Safety status monitoring and configuration settings page for the Web UI."""

from __future__ import annotations

from pathlib import Path
try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

from sandbox.copier import compute_directory_fingerprint
import web.components as components
import web.state as state


def render() -> None:
    """Render the safety audit, integrity verification, and LLM configuration view."""
    if st is None:
        return

    st.header("🛡️ Safety Controls & Configuration Settings")
    st.caption("Inspect live repository immutability, verify safety invariant enforcement, and configure runtime providers.")

    tab_safety, tab_llm, tab_session = st.tabs(["🔒 Safety Invariants", "🧠 LLM & Retrieval Config", "🔄 Session Management"])

    # 1. Safety Invariants Tab
    with tab_safety:
        st.subheader("Repository Integrity & Fingerprint Status")
        repo_path = state.get_repo_path()
        initial_hash = state.get_initial_sha256()

        if repo_path and initial_hash:
            st.write(f"**Target Repository:** `{repo_path}`")
            st.write(f"**Baseline SHA-256:** `{initial_hash}`")

            # Real-time live immutability check
            try:
                current_hash = compute_directory_fingerprint(Path(repo_path))
                if current_hash == initial_hash:
                    st.success("✅ **Live Immutability Verified:** Target repository is 100% byte-for-byte identical to baseline.")
                else:
                    st.error("🚨 **Integrity Alert:** Repository contents have changed on disk since initial load!")
            except Exception as e:
                st.warning(f"Could not compute live fingerprint: {e}")
        else:
            st.info("No repository is currently loaded.")

        st.divider()

        st.subheader("Enforced Project Safety Invariants")
        st.markdown(
            """
            - **Strict Read-Only Target:** Ingestion, AST analysis, graph building, chunking, and verification never write to the target directory.
            - **Isolated Temporary Sandboxes:** All patch application and test runs execute in disposable directories created via `tempfile.mkdtemp()`.
            - **Mandatory Human Approval Gate:** Automated patches cannot be applied without explicit confirmation.
            - **Safety Classification Tiers:**
              - `SAFE_AUTOMATIC_PROPOSAL`: Eligible for sandbox testing upon human approval.
              - `REVIEW_REQUIRED`: Blocked from automated application; requires manual developer intervention.
              - `UNSUPPORTED`: Informational finding without automated refactoring strategy.
            - **Stale-Source Detection:** Validates that source files have not diverged prior to applying patches.
            - **Secret Redaction:** High-entropy credentials, tokens, and API keys are scrubbed from reports and logs.
            """
        )

    # 2. LLM & Retrieval Settings Tab
    with tab_llm:
        st.subheader("LLM Provider & Model Settings")
        llm_cfg = state.get_llm_config()

        mock_mode = st.toggle(
            "Offline / Mock Provider",
            value=llm_cfg.get("mock_mode", True),
            help="Enable deterministic offline mode (FakeLLMProvider) without requiring an OpenAI API key.",
        )

        api_key = st.text_input(
            "OpenAI API Key:",
            value=llm_cfg.get("api_key", ""),
            type="password",
            disabled=mock_mode,
            help="Stored only in memory in the active Streamlit session. Never written to disk.",
        )

        c1, c2 = st.columns(2)
        model_name = c1.selectbox("Chat Model:", ["gpt-4o-mini", "gpt-4o"], index=0, disabled=mock_mode)
        embedding_model = c2.selectbox(
            "Embedding Model:",
            ["text-embedding-3-small", "text-embedding-3-large"],
            index=0,
            disabled=mock_mode,
        )

        if st.button("Save Model Settings", type="primary"):
            state.set_llm_config({
                "mock_mode": mock_mode,
                "api_key": api_key,
                "model": model_name,
                "embedding_model": embedding_model,
            })
            st.success("Model settings saved for this session!")

    # 3. Session Management Tab
    with tab_session:
        st.subheader("Session Cache & State")
        st.write("Resetting the session clears all parsed models, graphs, and reports while retaining your selected repository path.")

        if st.button("🔄 Flush Session Cache", type="secondary"):
            state.reset_session_cache()
            st.success("Session cache flushed!")
            st.rerun()
