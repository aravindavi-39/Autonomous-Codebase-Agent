"""Centralized session state management for the Autonomous Codebase Agent Web UI.

Provides typed accessors, cache management, and safe state access for all web pages.
Encapsulates Streamlit session state keys to ensure consistency and prevent key collisions.
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

if TYPE_CHECKING:
    from analysis.findings.context import AnalysisContext
    from analysis.findings.models import AnalysisReport
    from analysis.graph_models import CodeGraph
    from analysis.models import RepositoryCodeIndex
    from ingestion.models import RepositoryManifest
    from refactoring.models import RefactoringPlan
    from sandbox.models import SandboxReport, SandboxSession
    from verification.models import VerificationReport


# ---------------------------------------------------------------------------
# State Keys
# ---------------------------------------------------------------------------
KEY_REPO_PATH = "repo_path"
KEY_INITIAL_SHA256 = "initial_sha256"
KEY_MANIFEST = "manifest"
KEY_CODE_INDEX = "code_index"
KEY_CODE_GRAPH = "code_graph"
KEY_ANALYSIS_CONTEXT = "analysis_context"
KEY_ANALYSIS_REPORT = "analysis_report"
KEY_REFACTORING_PLAN = "refactoring_plan"
KEY_SANDBOX_REPORT = "sandbox_report"
KEY_SANDBOX_RESULT = "sandbox_result"  # Alias for session
KEY_VERIFICATION_REPORT = "verification_report"
KEY_VERIFICATION_RESULT = "verification_result"  # Alias
KEY_QA_HISTORY = "qa_history"
KEY_LLM_CONFIG = "llm_config"
KEY_RETRIEVAL_CONFIG = "retrieval_config"
KEY_ACTIVE_PAGE = "active_page"


def _get_state() -> dict[str, Any]:
    """Retrieve the current Streamlit session_state dict safely."""
    if st is not None and hasattr(st, "session_state"):
        return st.session_state
    return {}


# ---------------------------------------------------------------------------
# Repository & Integrity
# ---------------------------------------------------------------------------
def is_repo_loaded() -> bool:
    """Return True if a repository manifest is loaded in session state."""
    return get_manifest() is not None


def get_repo_path() -> Optional[str]:
    """Return the selected repository path."""
    return _get_state().get(KEY_REPO_PATH)


def set_repo_path(path: str) -> None:
    """Set the selected repository path."""
    if st is not None:
        st.session_state[KEY_REPO_PATH] = path


def get_initial_sha256() -> Optional[str]:
    """Return the baseline SHA-256 fingerprint of the repository."""
    return _get_state().get(KEY_INITIAL_SHA256)


def set_initial_sha256(fingerprint: str) -> None:
    """Set the baseline SHA-256 fingerprint of the repository."""
    if st is not None:
        st.session_state[KEY_INITIAL_SHA256] = fingerprint


# ---------------------------------------------------------------------------
# Core Analysis Artifacts
# ---------------------------------------------------------------------------
def get_manifest() -> Optional[RepositoryManifest]:
    """Return the ingested repository manifest."""
    return _get_state().get(KEY_MANIFEST)


def set_manifest(manifest: RepositoryManifest) -> None:
    """Store the ingested repository manifest."""
    if st is not None:
        st.session_state[KEY_MANIFEST] = manifest


def get_code_index() -> Optional[RepositoryCodeIndex]:
    """Return the analyzed code index."""
    return _get_state().get(KEY_CODE_INDEX)


def set_code_index(code_index: RepositoryCodeIndex) -> None:
    """Store the analyzed code index."""
    if st is not None:
        st.session_state[KEY_CODE_INDEX] = code_index


def get_code_graph() -> Optional[CodeGraph]:
    """Return the built codebase relationship graph."""
    return _get_state().get(KEY_CODE_GRAPH)


def set_code_graph(code_graph: CodeGraph) -> None:
    """Store the built codebase relationship graph."""
    if st is not None:
        st.session_state[KEY_CODE_GRAPH] = code_graph


def get_analysis_context() -> Optional[AnalysisContext]:
    """Return the analysis context for findings and diff generation."""
    return _get_state().get(KEY_ANALYSIS_CONTEXT)


def set_analysis_context(ctx: AnalysisContext) -> None:
    """Store the analysis context."""
    if st is not None:
        st.session_state[KEY_ANALYSIS_CONTEXT] = ctx


def get_analysis_report() -> Optional[AnalysisReport]:
    """Return the static analysis findings report."""
    return _get_state().get(KEY_ANALYSIS_REPORT)


def set_analysis_report(report: AnalysisReport) -> None:
    """Store the static analysis findings report."""
    if st is not None:
        st.session_state[KEY_ANALYSIS_REPORT] = report


def get_refactoring_plan() -> Optional[RefactoringPlan]:
    """Return the generated refactoring plan."""
    return _get_state().get(KEY_REFACTORING_PLAN)


def set_refactoring_plan(plan: RefactoringPlan) -> None:
    """Store the generated refactoring plan."""
    if st is not None:
        st.session_state[KEY_REFACTORING_PLAN] = plan


# ---------------------------------------------------------------------------
# Sandbox & Verification
# ---------------------------------------------------------------------------
def get_sandbox_report() -> Optional[SandboxReport]:
    """Return the latest sandbox execution report."""
    return _get_state().get(KEY_SANDBOX_REPORT)


def set_sandbox_report(report: SandboxReport) -> None:
    """Store the latest sandbox execution report and session."""
    if st is not None:
        st.session_state[KEY_SANDBOX_REPORT] = report
        st.session_state[KEY_SANDBOX_RESULT] = getattr(report, "session", report)


def get_sandbox_result() -> Optional[SandboxSession]:
    """Return the latest sandbox session result."""
    res = _get_state().get(KEY_SANDBOX_RESULT)
    if res is None:
        report = get_sandbox_report()
        if report and hasattr(report, "session"):
            return report.session
    return res


def set_sandbox_result(session: SandboxSession) -> None:
    """Store the sandbox session result."""
    if st is not None:
        st.session_state[KEY_SANDBOX_RESULT] = session


def get_verification_report() -> Optional[VerificationReport]:
    """Return the latest verification report."""
    report = _get_state().get(KEY_VERIFICATION_REPORT)
    if report is None:
        report = _get_state().get(KEY_VERIFICATION_RESULT)
    return report


def set_verification_report(report: VerificationReport) -> None:
    """Store the latest verification report."""
    if st is not None:
        st.session_state[KEY_VERIFICATION_REPORT] = report
        st.session_state[KEY_VERIFICATION_RESULT] = report


# ---------------------------------------------------------------------------
# Q&A & Configuration
# ---------------------------------------------------------------------------
def get_qa_history() -> list[dict[str, Any]]:
    """Return Q&A interaction history for current session."""
    return _get_state().setdefault(KEY_QA_HISTORY, [])


def add_qa_history_entry(entry: dict[str, Any]) -> None:
    """Append a Q&A interaction to history."""
    if st is not None:
        history = st.session_state.setdefault(KEY_QA_HISTORY, [])
        history.append(entry)


def get_llm_config() -> dict[str, Any]:
    """Return the LLM configuration settings."""
    default = {
        "mock_mode": True,
        "api_key": "",
        "model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
    }
    return _get_state().setdefault(KEY_LLM_CONFIG, default)


def set_llm_config(cfg: dict[str, Any]) -> None:
    """Update LLM configuration settings."""
    if st is not None:
        st.session_state[KEY_LLM_CONFIG] = cfg


def get_retrieval_config() -> dict[str, Any]:
    """Return retrieval parameters."""
    default = {
        "top_k": 5,
        "max_context": 12000,
        "use_semantic": True,
        "use_graph": True,
    }
    return _get_state().setdefault(KEY_RETRIEVAL_CONFIG, default)


def set_retrieval_config(cfg: dict[str, Any]) -> None:
    """Update retrieval parameters."""
    if st is not None:
        st.session_state[KEY_RETRIEVAL_CONFIG] = cfg


def get_active_page() -> str:
    """Return the active page name."""
    return _get_state().get(KEY_ACTIVE_PAGE, "Dashboard")


def set_active_page(page: str) -> None:
    """Set the active page name."""
    if st is not None:
        st.session_state[KEY_ACTIVE_PAGE] = page


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------
def reset_session_cache() -> None:
    """Reset cached codebase analysis in session state while preserving settings."""
    if st is None or not hasattr(st, "session_state"):
        return

    keys_to_clear = [
        KEY_MANIFEST,
        KEY_CODE_INDEX,
        KEY_CODE_GRAPH,
        KEY_ANALYSIS_CONTEXT,
        KEY_ANALYSIS_REPORT,
        KEY_REFACTORING_PLAN,
        KEY_SANDBOX_REPORT,
        KEY_SANDBOX_RESULT,
        KEY_VERIFICATION_REPORT,
        KEY_VERIFICATION_RESULT,
        KEY_INITIAL_SHA256,
        KEY_QA_HISTORY,
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
