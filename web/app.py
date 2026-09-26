"""Autonomous Codebase Understanding & Refactor Agent — Streamlit Web UI.

Phase 8.1 Stretch Goal:
Visual dashboard providing repository exploration, CodeGraph inspection,
grounded Q&A with validated citations, findings analysis, refactoring plan,
diff previews, sandbox application with approval gate, and verification audit.

Safety Invariants:
- The target repository is strictly read-only during analysis and Q&A.
- Refactoring application requires explicit human approval and runs exclusively
  inside isolated temporary sandboxes.
- The original repository remains 100% byte-for-byte unchanged (verified via SHA-256).
- No environment secrets or API keys are exposed.
"""

from __future__ import annotations

import os
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

# Core imports (reusing existing engines, no business logic duplication)
from analysis.analyzer import RepositoryAnalyzer
from analysis.findings.context import AnalysisContext
from analysis.findings.engine import AnalysisEngine
from analysis.findings.models import FindingCategory, Severity
from analysis.graph_builder import CodeGraphBuilder
from citations.validator import CitationValidator
from ingestion.pipeline import IngestionPipeline
from ingestion.validator import ValidationError, validate_repository_path
from llm.base import LLMConfigurationError, LLMError
from llm.fake_provider import FakeLLMProvider
from llm.openai_provider import OpenAIProvider
from refactoring.generator import DiffGenerator
from refactoring.models import SafetyClassification
from refactoring.planner import RefactoringPlanner
from retrieval.chunker import SemanticChunker
from retrieval.context_builder import ContextBuilder
from retrieval.qa_engine import QAEngine
from retrieval.retriever import HybridRetriever
from retrieval.vector_store import create_vector_store
from sandbox.copier import compute_directory_fingerprint
from sandbox.manager import SandboxManager
from verification.engine import VerificationEngine
from verification.models import PolicyMode, VerificationPolicy, VerificationVerdict


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_severity_badge_color(severity: Severity) -> str:
    """Return badge color for finding severity."""
    colors = {
        Severity.CRITICAL: "#d32f2f",
        Severity.HIGH: "#f57c00",
        Severity.MEDIUM: "#fbc02d",
        Severity.LOW: "#0288d1",
        Severity.INFO: "#757575",
    }
    return colors.get(severity, "#757575")


def get_safety_badge_color(safety: SafetyClassification) -> str:
    """Return badge color for refactoring safety tier."""
    colors = {
        SafetyClassification.SAFE_AUTOMATIC_PROPOSAL: "#2e7d32",
        SafetyClassification.REVIEW_REQUIRED: "#ed6c02",
        SafetyClassification.UNSUPPORTED: "#d32f2f",
    }
    return colors.get(safety, "#757575")


def format_citation_markdown(citation: Any) -> str:
    """Format a verified citation into clean markdown."""
    if hasattr(citation, "format_citation"):
        return citation.format_citation(show_entity=True)
    file_val = getattr(citation, "file", None) or getattr(citation, "file_path", "unknown")
    start = getattr(citation, "start_line", 1)
    end = getattr(citation, "end_line", start)
    entity_part = f" ({citation.entity})" if getattr(citation, "entity", None) else ""
    return f"📄 `{file_val}:{start}-{end}`{entity_part}"


def reset_session_cache() -> None:
    """Reset cached codebase analysis in session state."""
    for key in [
        "manifest",
        "code_index",
        "code_graph",
        "analysis_report",
        "refactoring_plan",
        "qa_engine",
        "initial_sha256",
        "sandbox_result",
        "verification_result",
    ]:
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Main Streamlit Application
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Autonomous Codebase Agent",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Top Header
    st.title("🛡️ Autonomous Codebase Understanding & Refactor Agent")
    st.caption("AI-powered agent for deep repository analysis, grounded Q&A, and safe sandbox refactoring.")

    # Real-time Safety Banner
    st.info(
        "🔒 **Safety Invariant Active:** Original target repositories are strictly read-only. "
        "All code refactorings require explicit approval and execute exclusively inside isolated temporary sandboxes.",
        icon="ℹ️",
    )

    # -----------------------------------------------------------------------
    # Sidebar: Repository Selection & Configuration
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
            reset_session_cache()
            st.rerun()

        st.divider()

        # LLM Provider Configuration
        st.header("🧠 Q&A Model Settings")
        mock_mode = st.toggle("Offline / Mock Mode", value=True, help="Run without OpenAI API keys using deterministic mock provider.")
        top_k = st.slider("Top Chunks (k)", min_value=1, max_value=15, value=5)
        max_context = st.slider("Max Context Chars", min_value=2000, max_value=30000, value=12000, step=1000)
        use_semantic = st.checkbox("Semantic Vector Search", value=True)
        use_graph = st.checkbox("Structural Graph Traversal", value=True)

        st.divider()

        # Safety & Status Indicators
        st.header("🛡️ Safety & Integrity")
        if "initial_sha256" in st.session_state:
            st.success("Target Repo: Fingerprinted")
            st.caption(f"SHA-256: `{st.session_state['initial_sha256'][:16]}...`")
        else:
            st.info("Target Repo: Not Loaded")

        st.markdown(
            """
            - **Target:** Read-Only
            - **Sandbox:** Ephemeral Tempdir
            - **Approval:** Strictly Mandatory
            - **Secrets:** Redacted & Filtered
            """
        )

    # -----------------------------------------------------------------------
    # Loading & Ingestion Pipeline Trigger
    # -----------------------------------------------------------------------
    if load_clicked:
        try:
            with st.spinner("Validating and ingesting repository..."):
                reset_session_cache()
                resolved_path = validate_repository_path(repo_path_input)

                # Fingerprint target repo before anything runs
                initial_hash = compute_directory_fingerprint(resolved_path)
                st.session_state["initial_sha256"] = initial_hash
                st.session_state["repo_path"] = str(resolved_path)

                # 1. Ingestion
                pipeline = IngestionPipeline()
                manifest = pipeline.ingest(str(resolved_path))
                st.session_state["manifest"] = manifest

                # 2. AST Code Analysis
                analyzer = RepositoryAnalyzer()
                code_index = analyzer.analyze_repository(str(resolved_path), manifest=manifest)
                st.session_state["code_index"] = code_index

                # 3. CodeGraph Building
                builder = CodeGraphBuilder()
                code_graph = builder.build_graph(code_index)
                st.session_state["code_graph"] = code_graph

                # 4. Findings Analysis
                findings_engine = AnalysisEngine()
                analysis_report = findings_engine.analyze(
                    manifest=manifest,
                    code_index=code_index,
                    code_graph=code_graph,
                    root_path=resolved_path,
                )
                st.session_state["analysis_report"] = analysis_report

                # 5. Refactoring Plan
                context = AnalysisContext(
                    manifest=manifest,
                    code_index=code_index,
                    code_graph=code_graph,
                )
                st.session_state["analysis_context"] = context
                planner = RefactoringPlanner()
                plan = planner.plan(report=analysis_report, context=context)
                st.session_state["refactoring_plan"] = plan

            st.success(f"Successfully loaded and analyzed **{manifest.name}**!")
        except ValidationError as exc:
            st.error(f"Path Validation Error: {exc}")
            return
        except Exception as exc:
            st.error(f"Analysis Error: {exc}")
            return

    # Check if a repository is currently loaded
    manifest = st.session_state.get("manifest")
    code_index = st.session_state.get("code_index")
    code_graph = st.session_state.get("code_graph")
    analysis_report = st.session_state.get("analysis_report")
    refactoring_plan = st.session_state.get("refactoring_plan")
    repo_path_str = st.session_state.get("repo_path")

    if not manifest:
        st.warning("👈 Please select a repository in the sidebar and click **Load & Analyze** to begin.")
        return

    # -----------------------------------------------------------------------
    # Main Content Area: 6 Navigation Tabs
    # -----------------------------------------------------------------------
    tab_overview, tab_graph, tab_qa, tab_findings, tab_refactor, tab_verify = st.tabs(
        [
            "📊 Overview",
            "🕸️ CodeGraph",
            "💬 Ask Codebase",
            "🔍 Findings",
            "🛠️ Refactoring & Diffs",
            "🧪 Sandbox & Verification",
        ]
    )

    # =======================================================================
    # TAB 1: Overview
    # =======================================================================
    with tab_overview:
        st.subheader(f"Repository Overview: {manifest.name}")
        st.write(f"**Path:** `{repo_path_str}`")

        stats = manifest.statistics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Files", f"{stats.total_files:,}")
        col2.metric("Directories", f"{stats.total_directories:,}")
        col3.metric("Lines of Code", f"{stats.total_lines:,}")
        col4.metric("Tests", len(stats.test_files))
        col5.metric("Configs", len(stats.configuration_files))

        st.divider()

        col_lang, col_class = st.columns([1, 1])
        with col_lang:
            st.markdown("### 🌐 Detected Languages")
            if stats.files_by_language:
                lang_data = [{"Language": lang, "Files": count} for lang, count in stats.files_by_language.items()]
                st.dataframe(lang_data, use_container_width=True, hide_index=True)
            else:
                st.info("No supported languages detected.")

        with col_class:
            st.markdown("### 📑 Discovered Files Structure")
            files_display = [
                {
                    "Relative Path": f.relative_path,
                    "Language": f.language.value if hasattr(f.language, "value") else str(f.language),
                    "Lines": f.metadata.line_count,
                    "Size": f"{f.metadata.size_bytes} B",
                }
                for f in manifest.files
            ]
            st.dataframe(files_display, use_container_width=True, hide_index=True)

    # =======================================================================
    # TAB 2: CodeGraph & Architecture
    # =======================================================================
    with tab_graph:
        st.subheader("🕸️ CodeGraph Architecture & Relationships")
        if code_graph:
            graph_stats = code_graph.compute_statistics()

            col_g1, col_g2, col_g3, col_g4 = st.columns(4)
            col_g1.metric("Graph Nodes", graph_stats.total_nodes)
            col_g2.metric("Graph Edges", graph_stats.total_edges)
            col_g3.metric("Classes", len(code_index.classes) if code_index else 0)
            col_g4.metric("Functions", len(code_index.functions) if code_index else 0)

            st.divider()

            col_rel, col_hot = st.columns([1, 1])
            with col_rel:
                st.markdown("### 🔗 Relationship Types")
                if graph_stats.relationships_by_type:
                    rel_data = [
                        {"Relationship": rel, "Count": count}
                        for rel, count in graph_stats.relationships_by_type.items()
                    ]
                    st.dataframe(rel_data, use_container_width=True, hide_index=True)
                else:
                    st.info("No inter-module relationships found.")

            with col_hot:
                st.markdown("### 🔁 Circular Dependencies & Hotspots")
                if graph_stats.circular_dependencies:
                    for cycle in graph_stats.circular_dependencies:
                        st.error(f"Cycle Detected: `{cycle.cycle_str}`")
                else:
                    st.success("✅ Zero circular dependencies detected.")

                if graph_stats.most_depended_on_modules:
                    st.markdown("**Top Depended-On Modules:**")
                    for mod, count in graph_stats.most_depended_on_modules[:5]:
                        st.write(f"- `{mod}` ({count} references)")

    # =======================================================================
    # TAB 3: Codebase Q&A
    # =======================================================================
    with tab_qa:
        st.subheader("💬 Ask Questions About the Codebase")
        st.caption("Ask natural-language architectural questions backed by semantic vector search and verified source citations.")

        sample_questions = [
            "What does this codebase do and what are its entry points?",
            "What functions are defined in src/calculator.py and how are they implemented?",
            "Are there any mutable default arguments or potential bugs in this codebase?",
        ]
        selected_sample = st.selectbox("Sample Questions:", ["(Select a question...)"] + sample_questions)
        default_q = selected_sample if selected_sample != "(Select a question...)" else ""

        user_question = st.text_input("Your Question:", value=default_q, placeholder="Ask how a module or function works...")
        ask_btn = st.button("🔎 Submit Question", type="primary")

        if ask_btn and user_question.strip():
            with st.spinner("Searching codebase and synthesizing answer..."):
                try:
                    # Setup LLM Provider
                    if mock_mode:
                        provider = FakeLLMProvider()
                    else:
                        provider = OpenAIProvider()
                        provider._get_client()

                    # Semantic Chunking & Vector Store
                    root_path = Path(manifest.root_path)
                    chunker = SemanticChunker(root_path=root_path)
                    chunks = chunker.chunk_repository(manifest=manifest, code_index=code_index)

                    vector_store = create_vector_store()
                    if use_semantic:
                        vector_store.index(chunks, provider=provider)

                    # Retrieval & QA Engine
                    citation_validator = CitationValidator(manifest=manifest, code_index=code_index)
                    retriever = HybridRetriever(
                        vector_store=vector_store,
                        code_graph=code_graph,
                        code_index=code_index,
                    )
                    context_builder = ContextBuilder(max_chunks=top_k, max_context_chars=max_context)
                    qa_engine = QAEngine(
                        retriever=retriever,
                        llm_provider=provider,
                        citation_validator=citation_validator,
                        context_builder=context_builder,
                    )

                    response = qa_engine.ask(
                        question=user_question,
                        top_k=top_k,
                        max_context_chars=max_context,
                        use_semantic=use_semantic,
                        use_graph=use_graph,
                    )

                    # Display Answer
                    st.markdown("### Answer")
                    st.markdown(response.answer)

                    # Display Citations
                    st.markdown("### Verified Source Citations")
                    if response.citations:
                        for cit in response.citations:
                            st.markdown(format_citation_markdown(cit))
                    else:
                        st.info("No specific source citations matched.")

                    if response.is_grounded:
                        st.success("✅ Answer is verified and grounded in repository source code.")
                    else:
                        st.warning("⚠️ Insufficient evidence in retrieved chunks. Answer may be incomplete.")

                except LLMConfigurationError as exc:
                    st.error(f"Configuration Error: {exc}. Toggle 'Offline / Mock Mode' in sidebar to run offline.")
                except Exception as exc:
                    st.error(f"Q&A Execution Error: {exc}")

    # =======================================================================
    # TAB 4: Findings (Smells, Security, Patterns)
    # =======================================================================
    with tab_findings:
        st.subheader("🔍 Codebase Findings & Static Analysis")
        if analysis_report:
            findings = analysis_report.findings

            col_cat, col_sev = st.columns([1, 1])
            selected_cat = col_cat.selectbox(
                "Filter by Category:",
                options=["ALL", "SECURITY", "SMELL", "PATTERN"],
                index=0,
            )
            selected_sev = col_sev.selectbox(
                "Filter by Severity:",
                options=["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
                index=0,
            )

            filtered_findings = findings
            if selected_cat != "ALL":
                filtered_findings = [f for f in filtered_findings if f.category.value == selected_cat]
            if selected_sev != "ALL":
                filtered_findings = [f for f in filtered_findings if f.severity.value == selected_sev]

            st.write(f"Showing **{len(filtered_findings)}** of **{len(findings)}** findings:")

            if not filtered_findings:
                st.success("No findings match the selected filters.")
            else:
                for idx, finding in enumerate(filtered_findings, 1):
                    sev_color = get_severity_badge_color(finding.severity)
                    with st.expander(
                        f"#{idx} [{finding.severity.value}] {finding.title} — {finding.file}:{finding.start_line}",
                        expanded=(idx == 1),
                    ):
                        st.markdown(
                            f"**Finding ID:** `{finding.id}` | "
                            f"**Category:** `{finding.category.value}` | "
                            f"**Severity:** <span style='color:{sev_color};font-weight:bold'>{finding.severity.value}</span> | "
                            f"**Confidence:** `{finding.confidence.value}`",
                            unsafe_allow_html=True,
                        )
                        st.write(f"**Entity:** `{finding.entity}` in `{finding.file}:{finding.start_line}-{finding.end_line}`")
                        st.markdown(f"**Description:** {finding.description}")

                        if finding.evidence:
                            st.markdown("**Evidence:**")
                            st.code(finding.evidence, language="python")

                        st.markdown(f"**Why it matters:** {finding.rationale}")
                        st.info(f"💡 **Recommendation:** {finding.recommendation}")

    # =======================================================================
    # TAB 5: Refactoring Plan & Unified Diffs
    # =======================================================================
    with tab_refactor:
        st.subheader("🛠️ Refactoring Plan & Unified Diff Previews")
        if refactoring_plan:
            actions = refactoring_plan.actions

            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            col_s1.metric("Total Proposals", len(actions))
            col_s2.metric("Safe Automatic", refactoring_plan.summary.safe_automatic)
            col_s3.metric("Review Required", refactoring_plan.summary.review_required)
            col_s4.metric("Unsupported", refactoring_plan.summary.unsupported)

            st.divider()

            if not actions:
                st.info("No refactoring proposals available for this codebase.")
            else:
                diff_gen = DiffGenerator()
                for idx, action in enumerate(actions, 1):
                    proposal = action.proposal
                    safety_color = get_safety_badge_color(proposal.safety)

                    with st.expander(
                        f"Action #{idx}: {proposal.strategy} on {proposal.source_file} ({proposal.safety.value})",
                        expanded=(idx == 1),
                    ):
                        st.markdown(
                            f"**Safety Classification:** <span style='color:{safety_color};font-weight:bold'>{proposal.safety.value}</span> | "
                            f"**Target Finding:** `{proposal.finding_id}`",
                            unsafe_allow_html=True,
                        )
                        st.write(f"**Strategy:** `{proposal.strategy}`")
                        st.write(f"**File:** `{proposal.source_file}` (Lines {proposal.source_start_line}–{proposal.source_end_line})")
                        st.write(f"**Description:** {proposal.description}")
                        st.write(f"**Rationale:** {proposal.rationale}")

                        # Generate Unified Diff
                        try:
                            context = st.session_state.get("analysis_context")
                            if context:
                                diff_results = diff_gen.generate(proposal=proposal, context=context)
                                diff_text = "\n".join(d.diff_text for d in diff_results if d.diff_text)
                                if diff_text:
                                    st.markdown("**Unified Diff Preview:**")
                                    st.code(diff_text, language="diff")
                                else:
                                    st.info("No diff available for this proposal.")
                            else:
                                st.info("Analysis context unavailable.")
                        except Exception as diff_exc:
                            st.warning(f"Could not generate diff: {diff_exc}")

    # =======================================================================
    # TAB 6: Sandbox Application & Verification
    # =======================================================================
    with tab_verify:
        st.subheader("🧪 Safe Sandbox Application & Multi-Layer Verification")
        st.caption("Apply proposed diffs inside isolated disposable sandboxes and audit resolution without touching original code.")

        st.warning(
            "⚠️ **Human Approval Boundary:** The original repository is NEVER modified. "
            "Refactoring proposals can only be applied to temporary copies in isolated directories with explicit approval.",
            icon="🛡️",
        )

        # 1. Sandbox Application
        st.markdown("### 1. Apply Proposal to Isolated Sandbox")
        if refactoring_plan and refactoring_plan.actions:
            proposal_options = {
                f"{act.proposal.finding_id} — {act.proposal.strategy} ({act.proposal.safety.value})": act
                for act in refactoring_plan.actions
            }
            selected_proposal_key = st.selectbox("Select Proposal to Apply:", options=list(proposal_options.keys()))
            selected_action = proposal_options[selected_proposal_key]
            selected_prop = selected_action.proposal

            is_safe = selected_prop.safety == SafetyClassification.SAFE_AUTOMATIC_PROPOSAL
            if not is_safe:
                st.error(
                    f"⛔ Cannot apply `{selected_prop.safety.value}` action to sandbox. Only `SAFE_AUTOMATIC_PROPOSAL` actions are eligible."
                )

            approval_checked = st.checkbox(
                "✅ I explicitly confirm and approve applying this refactoring patch to an isolated sandbox copy.",
                value=False,
                disabled=not is_safe,
            )

            col_app1, col_app2 = st.columns([1, 1])
            apply_btn = col_app1.button(
                "🚀 Apply to Sandbox",
                type="primary",
                disabled=(not is_safe or not approval_checked),
                use_container_width=True,
            )

            if apply_btn:
                with st.spinner("Creating sandbox, running baseline tests, applying patch, and running post-patch tests..."):
                    try:
                        sandbox_mgr = SandboxManager()
                        report = sandbox_mgr.execute_session(
                            source_path=Path(manifest.root_path),
                            proposal=selected_prop,
                            approved=True,
                            keep_sandbox=False,
                            audit_verification=True,
                            baseline_findings=analysis_report.findings if analysis_report else None,
                        )
                        st.session_state["sandbox_result"] = report.session
                        st.success(f"Sandbox Session `{report.session.id}` completed successfully!")
                    except Exception as s_exc:
                        st.error(f"Sandbox Application Error: {s_exc}")

            # Display Sandbox Session Results
            session = st.session_state.get("sandbox_result")
            if session:
                st.markdown("#### Sandbox Execution Report")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Session ID", session.id)
                c2.metric("Approval Status", session.approval_status.value)
                patch_status_str = session.patch_result.status.value if session.patch_result else "SKIPPED"
                c3.metric("Patch Status", patch_status_str)
                regression_verdict = session.test_comparison.regression_status.value if session.test_comparison else "SKIPPED"
                reg_color = "green" if regression_verdict == "PASS" else "red"
                c4.markdown(f"**Verdict:** <span style='color:{reg_color};font-size:20px;font-weight:bold'>{regression_verdict}</span>", unsafe_allow_html=True)

                base_summary = session.test_comparison.baseline_run.summary if session.test_comparison and session.test_comparison.baseline_run else "None"
                patch_summary = session.test_comparison.patched_run.summary if session.test_comparison and session.test_comparison.patched_run else "None"
                st.write(f"**Baseline Tests:** {base_summary}")
                st.write(f"**Post-Patch Tests:** {patch_summary}")
                immut_status = "UNCHANGED (Verified SHA-256 match)" if session.source_intact else "MUTATED"
                st.write(f"**Original Repo Immutability:** `{immut_status}`")
                lifecycle_status = "CLEANED" if session.cleaned_up else f"RETAINED ({session.sandbox_path})"
                st.write(f"**Sandbox Lifecycle:** `{lifecycle_status}`")

        st.divider()

        # 2. Verification Audit Engine
        st.markdown("### 2. Standalone Verification Engine Audit")
        col_pol, col_tests, col_lint = st.columns([1, 1, 1])
        selected_policy_mode = col_pol.selectbox("Policy Mode:", ["STRICT", "LENIENT"], index=0)
        verify_run_tests = col_tests.checkbox("Run Subprocess Tests", value=True)
        verify_run_lint = col_lint.checkbox("Run AST Linter", value=True)

        verify_btn = st.button("🧪 Run Verification Audit on Repository", type="secondary")
        if verify_btn:
            with st.spinner("Running full verification audit (tests, linter, findings, immutability)..."):
                try:
                    policy = (
                        VerificationPolicy.strict()
                        if selected_policy_mode == "STRICT"
                        else VerificationPolicy.lenient()
                    )
                    v_engine = VerificationEngine()
                    v_report = v_engine.verify_repository(
                        repo_path=Path(manifest.root_path),
                        policy=policy,
                        run_tests=verify_run_tests,
                        run_lint=verify_run_lint,
                    )
                    st.session_state["verification_result"] = v_report
                except Exception as v_exc:
                    st.error(f"Verification Error: {v_exc}")

        v_report = st.session_state.get("verification_result")
        if v_report:
            st.markdown("#### Repository Verification Report")
            v_color = "green" if v_report.verdict == VerificationVerdict.PASSED else "red"
            st.markdown(
                f"**Overall Verdict:** <span style='color:{v_color};font-size:22px;font-weight:bold'>{v_report.verdict.value}</span> (Policy: `{v_report.policy.mode.value}`)",
                unsafe_allow_html=True,
            )

            # Details table
            verif_rows = []
            if v_report.test_run:
                verif_rows.append({
                    "Check": "Unit Tests",
                    "Status": v_report.test_run.status,
                    "Details": v_report.test_run.summary,
                })
            elif v_report.test_skipped:
                verif_rows.append({"Check": "Unit Tests", "Status": "SKIPPED", "Details": "Test execution skipped by user request."})

            if v_report.lint_run:
                verif_rows.append({
                    "Check": "AST Lint & Syntax",
                    "Status": v_report.lint_run.status.value,
                    "Details": v_report.lint_run.summary,
                })
            elif v_report.lint_skipped:
                verif_rows.append({"Check": "AST Lint & Syntax", "Status": "SKIPPED", "Details": "Linting skipped by user request."})

            verif_rows.append({
                "Check": "Repo Immutability",
                "Status": "UNCHANGED" if v_report.source_intact else "MUTATED",
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


if __name__ == "__main__":
    main()
