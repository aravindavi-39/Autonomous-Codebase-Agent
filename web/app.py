"""Autonomous Codebase Understanding & Refactor Agent — Streamlit Web UI.

Unified multi-page application integrating all implemented functionality (Phases 0 through 8):
- Phase 1: Repository Ingestion & Manifest Generation
- Phase 2: AST Code Understanding & Structure
- Phase 3: CodeGraph Architecture & Relationship Traversal
- Phase 4: Grounded Codebase Q&A with Validated Citations
- Phase 5: Static Security & Code Smell Analysis
- Phase 6: Refactoring Planning & Unified Diff Previews
- Phase 7: Safe Sandbox Execution with Human Approval Boundary
- Phase 8: Multi-Check Verification Engine & Resolution Audit

Safety Invariants:
- The target repository is strictly read-only during analysis and Q&A.
- Refactoring application requires explicit human approval and runs exclusively inside isolated temporary sandboxes.
- The original repository remains 100% byte-for-byte unchanged (verified via SHA-256).
- No environment secrets or API keys are exposed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Ensure project root and src/ are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    import streamlit as st
except ImportError:
    print(
        "Streamlit is not installed. To run the web interface, install optional dependencies:\n"
        "  pip install -r requirements-web.txt\n"
        "or\n"
        "  pip install \".[web]\""
    )
    sys.exit(1)

# Core engine imports
from analysis.analyzer import RepositoryAnalyzer
from analysis.findings.context import AnalysisContext
from analysis.findings.engine import AnalysisEngine
from analysis.findings.models import Severity
from analysis.graph_builder import CodeGraphBuilder
from ingestion.pipeline import IngestionPipeline
from ingestion.validator import ValidationError, validate_repository_path
from refactoring.models import SafetyClassification
from refactoring.planner import RefactoringPlanner
from sandbox.copier import compute_directory_fingerprint

# Web UI infrastructure imports
import web.components as components
import web.state as state

# Page module imports
import web.pages.dashboard as page_dashboard
import web.pages.repository as page_repository
import web.pages.code_understanding as page_code_understanding
import web.pages.architecture as page_architecture
import web.pages.qa as page_qa
import web.pages.findings as page_findings
import web.pages.refactoring as page_refactoring
import web.pages.sandbox as page_sandbox
import web.pages.verification as page_verification
import web.pages.reports as page_reports
import web.pages.safety as page_safety


# ---------------------------------------------------------------------------
# Backward-Compatible Public Re-Exports (Preserves Phase 8.1 API)
# ---------------------------------------------------------------------------
get_severity_badge_color = components.get_severity_badge_color
get_safety_badge_color = components.get_safety_badge_color
format_citation_markdown = components.format_citation_markdown
reset_session_cache = state.reset_session_cache


# ---------------------------------------------------------------------------
# Page Routing Table
# ---------------------------------------------------------------------------
PAGES = {
    "📊 Dashboard": page_dashboard.render,
    "📁 Repository & Ingestion": page_repository.render,
    "🧠 Code Understanding": page_code_understanding.render,
    "🕸️ Architecture & Graph": page_architecture.render,
    "💬 Codebase Q&A": page_qa.render,
    "🔍 Findings & Security": page_findings.render,
    "🛠️ Refactoring & Diffs": page_refactoring.render,
    "🧪 Sandbox Apply": page_sandbox.render,
    "📋 Verification Engine": page_verification.render,
    "📑 Reports & Exports": page_reports.render,
    "🛡️ Safety & Settings": page_safety.render,
}


# ---------------------------------------------------------------------------
# Main Application Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="Autonomous Codebase Agent",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Top Header Banner
    st.title("🛡️ Autonomous Codebase Understanding & Refactor Agent")
    st.caption("AI-powered agent for deep repository analysis, grounded architectural Q&A, and safe sandbox refactoring.")
    components.render_safety_banner()

    # -----------------------------------------------------------------------
    # Persistent Sidebar
    # -----------------------------------------------------------------------
    with st.sidebar:
        st.header("📁 Repository Selection")

        preset_repos = [
            "tests/fixtures/sandbox_test_repo",
            "tests/fixtures/vulnerable_repo",
        ]
        preset_choice = st.selectbox(
            "Select Preset or Custom:",
            options=["Custom Path"] + preset_repos,
            index=1,
            help="Choose a pre-packaged test fixture or enter your own local path.",
        )

        if preset_choice == "Custom Path":
            repo_path_input = st.text_input(
                "Local Repository Path:",
                value="tests/fixtures/sandbox_test_repo",
                help="Absolute or relative path to a local code repository.",
            )
        else:
            repo_path_input = preset_choice

        col_load, col_clear = st.columns([1, 1])
        load_clicked = col_load.button("🚀 Load & Analyze", type="primary", use_container_width=True)
        if col_clear.button("🔄 Reset", use_container_width=True):
            state.reset_session_cache()
            st.rerun()

        # Ingestion & Analysis Execution
        if load_clicked:
            try:
                with st.spinner("Validating, ingesting, and analyzing repository..."):
                    state.reset_session_cache()
                    resolved_path = validate_repository_path(repo_path_input)

                    # Compute baseline fingerprint before any operation
                    initial_hash = compute_directory_fingerprint(resolved_path)
                    state.set_initial_sha256(initial_hash)
                    state.set_repo_path(str(resolved_path))

                    # 1. Ingestion Pipeline
                    pipeline = IngestionPipeline()
                    manifest = pipeline.ingest(str(resolved_path))
                    state.set_manifest(manifest)

                    # 2. AST Code Analysis
                    analyzer = RepositoryAnalyzer()
                    code_index = analyzer.analyze_repository(str(resolved_path), manifest=manifest)
                    state.set_code_index(code_index)

                    # 3. CodeGraph Construction
                    builder = CodeGraphBuilder()
                    code_graph = builder.build_graph(code_index)
                    state.set_code_graph(code_graph)

                    # 4. Static Findings Analysis
                    findings_engine = AnalysisEngine()
                    analysis_report = findings_engine.analyze(
                        manifest=manifest,
                        code_index=code_index,
                        code_graph=code_graph,
                        root_path=resolved_path,
                    )
                    state.set_analysis_report(analysis_report)

                    # 5. Refactoring Plan
                    context = AnalysisContext(
                        manifest=manifest,
                        code_index=code_index,
                        code_graph=code_graph,
                        root_path=resolved_path,
                    )
                    state.set_analysis_context(context)
                    planner = RefactoringPlanner()
                    plan = planner.plan(report=analysis_report, context=context)
                    state.set_refactoring_plan(plan)

                st.success(f"Loaded **{manifest.name}** successfully!")
            except ValidationError as exc:
                st.error(f"Path Validation Error: {exc}")
            except Exception as exc:
                st.error(f"Analysis Pipeline Error: {exc}")

        st.divider()

        # Navigation
        st.header("🧭 Navigation")
        selected_page = st.radio(
            "Go to Page:",
            options=list(PAGES.keys()),
            index=0,
            label_visibility="collapsed",
        )

        st.divider()

        # Safety & Integrity Indicators
        st.header("🛡️ Safety & Integrity")
        components.render_sha256_status()
        st.markdown(
            """
            - **Target:** Strictly Read-Only
            - **Sandbox:** Ephemeral Tempdir
            - **Approval:** Strictly Mandatory
            - **Secrets:** Redacted & Filtered
            """
        )

    # -----------------------------------------------------------------------
    # Main Page Dispatch
    # -----------------------------------------------------------------------
    render_func = PAGES.get(selected_page, page_dashboard.render)
    render_func()


if __name__ == "__main__":
    main()
