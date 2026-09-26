# Implementation Plan: Unified Streamlit Web Application (Phase 0–8 Integration)

**Project:** Autonomous-Codebase-Agent  
**Target File:** `implementation_plan.md`  
**Date:** 2026-09-26  
**Status:** PROPOSED (Pending Approval)

---

## 1. Objective

Transform the existing standalone Streamlit UI (`web/app.py`, created in Phase 8.1) into a complete, modular, unified multi-page web application that surfaces the full capabilities of **all implemented phases (Phases 0 through 8)**:
- **Phase 0:** Bootstrap, environment, configuration, and project structure
- **Phase 1:** Repository Ingestion, path validation, metadata extraction, language detection, and manifest generation
- **Phase 2:** AST parsing, code understanding, class/function/call/import models
- **Phase 3:** Codebase relationship graph, dependency indexing, caller/callee lookups, and circular dependency detection
- **Phase 4:** Codebase Q&A with hybrid vector/graph retrieval, groundness verification, and source citation validation
- **Phase 5:** Static code analysis, security vulnerability scanning, code smell detection, and pattern analysis
- **Phase 6:** Refactoring planning, deterministic strategy selection, and validated unified diff generation
- **Phase 7:** Safe sandbox execution, pre/post SHA-256 fingerprinting, baseline vs. post-patch test regression analysis, and strict human approval gating
- **Phase 8:** Multi-check verification engine, AST linting, target finding resolution audit, and delta finding analysis

### Strict Invariants & Boundaries
1. **Thin Presentation Layer:** The web layer must remain strictly presentation-only. Core modules (`src/`) must never import Streamlit or any web components.
2. **Zero Core Logic Duplication:** The web application will reuse existing engines, planners, managers, and data models directly.
3. **Preserve CLI Commands:** All existing CLI commands (`load`, `ask`, `analyze`, `graph`, `plan`, `diff`, `apply`, `verify`) must remain fully functional, untouched, and testable without Streamlit installed.
4. **Repository Immutability:** The target repository remains 100% read-only. All transformations, diff tests, and patches occur solely inside ephemeral sandbox copies. SHA-256 fingerprint verification is mandatory before and after all operations.
5. **Mandatory Human Approval:** Patch application must never trigger automatically or upon mere viewing. Explicit human confirmation is required prior to sandbox patch application.
6. **No Scope Creep:** No Phase 8.2+ stretch goals (tree-sitter, Git history analysis, SARIF, Docker sandboxing, plugins, multi-repo support) will be introduced.

---

## 2. Current Architecture Assumptions

The codebase currently comprises:
- `src/ingestion/`: `IngestionPipeline`, `validate_repository_path`, `RepositoryManifest`, `FileRecord`, `FileMetadata`
- `src/analysis/`: `RepositoryAnalyzer`, `RepositoryCodeIndex`, `ClassInfo`, `FunctionInfo`, `ImportInfo`, `CallInfo`
- `src/analysis/findings/`: `AnalysisEngine`, `AnalysisContext`, `Finding`, `AnalysisReport`, `FindingCategory`, `Severity`
- `src/analysis/graph_builder.py` & `src/analysis/graph_models.py`: `CodeGraphBuilder`, `CodeGraph`, `GraphNode`, `RelationshipEdge`, `GraphStatistics`, `CircularDependency`
- `src/citations/`: `Citation`, `CitationValidator`, `CitationValidationResult`
- `src/retrieval/`: `SemanticChunker`, `LocalVectorStore`, `create_vector_store`, `HybridRetriever`, `ContextBuilder`, `QAEngine`, `QAResponse`
- `src/llm/`: `LLMProvider`, `FakeLLMProvider`, `OpenAIProvider`, `LLMConfigurationError`
- `src/refactoring/`: `RefactoringPlanner`, `DiffGenerator`, `DiffValidator`, `ChangeProposal`, `RefactoringPlan`, `SafetyClassification`
- `src/sandbox/`: `SandboxManager`, `SandboxCopier`, `SandboxPatcher`, `SandboxTester`, `RegressionVerifier`, `SandboxCleanup`, `SandboxSession`, `SandboxReport`, `ApprovalStatus`, `compute_directory_fingerprint`
- `src/verification/`: `VerificationEngine`, `VerificationPolicy`, `VerificationReport`, `VerificationVerdict`, `FindingDelta`, `LintRunner`, `format_verification_table`
- `src/cli/main.py`: Typer CLI application orchestrating all core engines
- `web/app.py`: Phase 8.1 prototype containing a monolithic tab-based UI

---

## 3. Proposed Web Architecture

The monolithic `web/app.py` (~726 lines) will be decomposed into a clean, modular multi-page application with centralized session-state management and reusable components:

```
web/
├── __init__.py                  # Package marker & public re-exports
├── app.py                       # Main routing entry point, layout, and global sidebar
├── state.py                     # Centralized session state management & accessors
├── components.py                # Reusable UI widgets, badges, formatters, and cards
└── pages/
    ├── __init__.py              # Package marker
    ├── dashboard.py             # 1. Project-wide overview, health, and status
    ├── repository.py            # 2. File tree, language breakdown, file viewer
    ├── code_understanding.py    # 3. Classes, functions, methods, imports, calls
    ├── architecture.py          # 4. CodeGraph, dependencies, cycles, hotspots
    ├── qa.py                    # 5. Hybrid Q&A, citations, groundedness validation
    ├── findings.py              # 6. Security, code smells, patterns with filtering
    ├── refactoring.py           # 7. Refactoring proposals, actions, unified diff previews
    ├── sandbox.py               # 8. Sandbox application, approval gate, regression tests
    ├── verification.py          # 9. Read-only verification engine, policies, linting
    ├── reports.py               # 10. Centralized exports, JSON downloads, run audits
    └── safety.py                # 11. Safety status, SHA-256 audit, LLM configuration
```

### Architectural Principles
- **Entry Point (`web/app.py`):** Configures page settings, renders the persistent sidebar (repository selection, quick safety status, navigation radio), and dispatches rendering to the active page module.
- **Session State (`web/state.py`):** Encapsulates all access to `st.session_state` via typed helper functions. Isolates keys, avoids magic strings, and ensures cache consistency across pages.
- **Components (`web/components.py`):** Contains reusable presentation elements (severity badges, safety tier badges, citation formatters, diff highlighters, file size formatters, SHA-256 fingerprint cards).
- **Page Modules (`web/pages/*.py`):** Pure presentation controllers exposing a standardized `render()` function. Each page accesses state through `web/state.py` and triggers existing core engines as needed.

---

## 4. Page/Module Breakdown

### 1. Dashboard (`web/pages/dashboard.py`)
- **Purpose:** High-level summary of the active repository and analysis pipeline state.
- **Elements:**
  - Repository metadata card: name, path, resolved absolute path, SHA-256 fingerprint.
  - Top-level metrics row: Total Files, Total Lines of Code, Classes, Functions, Findings, Pending Proposals.
  - Pipeline Execution Status: visual badges showing whether Ingestion, AST Analysis, Graph Construction, Findings Analysis, and Refactoring Planning have been run.
  - Quick action buttons to jump to specific pages (e.g., "Inspect Findings", "Explore Architecture", "Review Refactorings").

### 2. Repository / Ingestion (`web/pages/repository.py`)
- **Purpose:** Deep dive into repository structure, file classifications, and content inspection.
- **Elements:**
  - Metrics: Total files, directories, size in bytes/KB/MB, test files count, configuration files count.
  - Language breakdown table & proportional progress bars.
  - Discovered files table: relative path, language, line count (`f.metadata.line_count`), size (`f.metadata.size_bytes`), binary flag.
  - Interactive file content viewer: dropdown to select any discovered text file and render its contents with syntax highlighting and line numbers.

### 3. Code Understanding (`web/pages/code_understanding.py`)
- **Purpose:** AST analysis explorer displaying extracted Python code constructs.
- **Elements:**
  - Summary counts: total classes, total functions, total methods, total imports, total calls, parse errors.
  - **Classes Explorer:** Filterable list of classes, base classes, decorators, docstring, and defined methods.
  - **Functions Explorer:** Filterable list of standalone functions and methods, arguments/parameter annotations, return types, async flag, and docstrings.
  - **Imports Explorer:** Breakdown of stdlib, third-party, and internal local imports.
  - **Calls Explorer:** Cross-module caller-callee invocation mapping.

### 4. Architecture / Code Graph (`web/pages/architecture.py`)
- **Purpose:** Visual and tabular inspection of structural dependencies and relationship graphs.
- **Elements:**
  - Graph metrics: total nodes, total edges, average connections.
  - Relationship type distribution table (`IMPORTS`, `DEFINES`, `CALLS`, `INHERITS`, `CONTAINS`, `TESTS`, `DEPENDS_ON`).
  - **Circular Dependency Detection:** Clear alert banners highlighting detected cycle paths (`A -> B -> C -> A`) or a green confirmation if acyclic.
  - **Hotspot Analysis:** Top depended-on modules and top importer modules.
  - **Entity Lookup:** Interactive query input to inspect neighbors, callers, callees, and dependencies of a specific module or class.

### 5. Q&A with Citations (`web/pages/qa.py`)
- **Purpose:** Natural language architectural question-answering with citation grounding.
- **Elements:**
  - Sample questions preset selector and custom query text input.
  - Search configuration toggles: semantic search (Chroma/Local vector store), structural traversal (CodeGraph), `top_k`, and `max_context_chars`.
  - Offline/Mock toggle vs. live OpenAI provider.
  - Formatted answer panel with clear separation between synthetic text and citations.
  - Verified source citation cards displaying file path, start-end line bounds, entity name, and code snippet.
  - Groundedness indicator badge (`Grounded in repository source` vs. `Insufficient evidence`).

### 6. Findings / Code Smells / Security (`web/pages/findings.py`)
- **Purpose:** Comprehensive presentation of detected static analysis findings.
- **Elements:**
  - Filter bar: Category filter (`ALL`, `SECURITY`, `CODE_SMELL`, `PATTERN`) and Severity filter (`ALL`, `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
  - Metric summary cards: total findings, security vulnerabilities, code smells, coding pattern issues.
  - Findings list inside interactive expanders featuring:
    - Unique finding ID, title, and category badge.
    - Color-coded severity badge and confidence level.
    - Source location (`file:start_line-end_line`) and target entity.
    - Detailed explanation and architectural rationale.
    - Verbatim code evidence snippet with syntax highlighting.
    - Actionable remediation recommendation.

### 7. Refactoring Plan and Diff (`web/pages/refactoring.py`)
- **Purpose:** Review proposed transformations and preview syntax-highlighted unified diffs.
- **Elements:**
  - Plan metrics: total proposals, safe automatic count, review required count, unsupported count.
  - Safety tier filter: toggle between all proposals or `SAFE_AUTOMATIC_PROPOSAL` only.
  - Proposal cards displaying strategy name, target finding ID, affected file, start/end lines, description, and rationale.
  - **Unified Diff Viewer:** Deterministically generates and renders standard unified diff syntax (`--- a/...`, `+++ b/...`, `@@ ... @@`) with additions/deletions highlighting.
  - Validation status of proposed diffs (ensuring syntax validity).
  - Download diff button (exports `.patch` file).

### 8. Sandbox / Apply with Explicit Approval (`web/pages/sandbox.py`)
- **Purpose:** Safe sandbox patch application with strict human approval gates.
- **Elements:**
  - Prominent safety disclaimer explaining sandbox isolation and repository immutability.
  - Proposal selector (restricted strictly to `SAFE_AUTOMATIC_PROPOSAL` actions).
  - Proposal details and targeted diff preview.
  - **Mandatory Approval Checkbox:** Explicit confirmation text required before the apply button unlocks.
  - Options: keep sandbox toggle (for manual inspection) and test execution timeout.
  - **Apply Execution:** Runs `SandboxManager.execute_session()` in a temporary isolated directory.
  - Session Results Display:
    - Session ID, creation timestamp, and approval status (`APPROVED` / `REJECTED`).
    - Patch application status and affected files.
    - Regression test verdict (`PASS`, `FAIL`, `BASELINE_FAILURE`, etc.).
    - Baseline vs. post-patch test run comparison tables (total, passed, failed, duration).
    - Sandbox cleanup status (`CLEANED` or path retained).
    - Source repository immutability verification check (pre/post SHA-256 comparison).

### 9. Verification (`web/pages/verification.py`)
- **Purpose:** Standalone verification engine audit and post-patch resolution assessment.
- **Elements:**
  - Verification target: active repository or optional target finding ID.
  - Policy selector: `STRICT` (fails on lint warnings) vs. `LENIENT`.
  - Execution options: enable/disable subprocess tests, enable/disable AST linter, timeout setting.
  - Run audit button (triggers `VerificationEngine.verify_repository()`).
  - Results Panel:
    - Overall verdict badge (`PASSED`, `FAILED`, `WARNING`).
    - Multi-check audit table: Unit Tests, AST Lint & Syntax, Finding Resolution, Repository Immutability.
    - Detailed lint violations table (file, line, column, code, message, severity).
    - Finding delta analysis (baseline count vs. post-patch count, target resolved indicator, zero newly introduced findings confirmation).
    - Observations, violations, and warnings.

### 10. Reports (`web/pages/reports.py`)
- **Purpose:** Centralized export center for all generated artifacts.
- **Elements:**
  - Tabular list of available reports based on current session state.
  - Export actions:
    - Repository Manifest JSON export.
    - Code Index JSON export (`code_index.export_json()`).
    - CodeGraph JSON export (`code_graph.export_json()`).
    - Analysis Findings JSON report (`analysis_report.to_json()`).
    - Refactoring Plan JSON export.
    - Unified Diff file download (`.patch`).
    - Sandbox Session Report JSON (`sandbox_report.to_json()`).
    - Verification Report JSON (`verification_report.to_json()`).
  - Interactive JSON preview with copy-to-clipboard functionality.

### 11. Safety / Settings (`web/pages/safety.py`)
- **Purpose:** Safety monitoring, repository integrity status, and runtime environment configuration.
- **Elements:**
  - **Repository Fingerprint Monitor:** Real-time pre-run and post-run SHA-256 hash display with verification badge.
  - **Safety Invariant Checklist:** Visual audit of active guarantees (read-only target, sandbox copy, approval barrier, secret redaction).
  - **LLM Settings:** Provider selection (`fake` vs. `openai`), API key management (stored strictly in memory/session-state, never logged or saved to disk), model selection, embedding model selection.
  - **Retrieval Parameters:** Default `top_k`, `max_context_chars`, chunk overlap settings.
  - **Cache & Session Management:** "Reset Session Cache" button with confirmation prompt to flush loaded models and reload cleanly.

---

## 5. Shared State Design

The Streamlit session state will be managed exclusively through helper functions in `web/state.py` using standardized keys:

| Key | Type | Description |
|---|---|---|
| `repo_path` | `str` | Path to currently selected target repository |
| `initial_sha256` | `str` | Pre-operation SHA-256 fingerprint of the target repository |
| `manifest` | `RepositoryManifest` | Ingestion manifest with file records and stats |
| `code_index` | `RepositoryCodeIndex` | AST analysis results (classes, functions, imports, calls) |
| `code_graph` | `CodeGraph` | Relationship graph with nodes, edges, and statistics |
| `analysis_context` | `AnalysisContext` | Context caching ASTs and disk file lines for rule execution |
| `analysis_report` | `AnalysisReport` | Detected findings (security, smells, patterns) |
| `refactoring_plan` | `RefactoringPlan` | Proposed refactoring actions and safety tiers |
| `sandbox_report` | `SandboxReport` | Execution report of the most recent sandbox session |
| `verification_report`| `VerificationReport`| Report from standalone or sandbox verification engine |
| `qa_history` | `list[dict]` | History of user questions, answers, and citations in current session |
| `llm_config` | `dict` | Provider type, API key, model names, temperature |
| `retrieval_config` | `dict` | `top_k`, `max_context_chars`, semantic/graph toggles |
| `active_page` | `str` | Current navigation destination |

### Typed State Helper Interface (`web/state.py`)
```python
def is_repo_loaded() -> bool: ...
def get_repo_path() -> Optional[str]: ...
def set_repo_path(path: str) -> None: ...
def get_initial_sha256() -> Optional[str]: ...
def set_initial_sha256(h: str) -> None: ...

def get_manifest() -> Optional[RepositoryManifest]: ...
def set_manifest(m: RepositoryManifest) -> None: ...

def get_code_index() -> Optional[RepositoryCodeIndex]: ...
def set_code_index(idx: RepositoryCodeIndex) -> None: ...

def get_code_graph() -> Optional[CodeGraph]: ...
def set_code_graph(g: CodeGraph) -> None: ...

def get_analysis_context() -> Optional[AnalysisContext]: ...
def set_analysis_context(ctx: AnalysisContext) -> None: ...

def get_analysis_report() -> Optional[AnalysisReport]: ...
def set_analysis_report(r: AnalysisReport) -> None: ...

def get_refactoring_plan() -> Optional[RefactoringPlan]: ...
def set_refactoring_plan(p: RefactoringPlan) -> None: ...

def get_sandbox_report() -> Optional[SandboxReport]: ...
def set_sandbox_report(sr: SandboxReport) -> None: ...

def get_verification_report() -> Optional[VerificationReport]: ...
def set_verification_report(vr: VerificationReport) -> None: ...

def get_llm_config() -> dict[str, Any]: ...
def set_llm_config(cfg: dict[str, Any]) -> None: ...

def reset_session_cache() -> None: ...
```

---

## 6. Data Flow

```
[User Selects Repository]
           │
           ▼
[validate_repository_path] ───(Fails)───► [Show Error Banner & Abort]
           │ (Passes)
           ▼
[compute_directory_fingerprint] ───► Store initial_sha256 in session_state
           │
           ▼
[IngestionPipeline.ingest()] ───► Store manifest in session_state
           │
           ▼
[RepositoryAnalyzer.analyze_repository()] ───► Store code_index in session_state
           │
           ▼
[CodeGraphBuilder.build_graph()] ───► Store code_graph in session_state
           │
           ▼
[AnalysisEngine.analyze()] ───► Store analysis_report in session_state
           │
           ▼
[AnalysisContext] + [RefactoringPlanner.plan()] ───► Store refactoring_plan in session_state
           │
           ├────────────────────────┬────────────────────────┐
           ▼                        ▼                        ▼
     [Pages 1–4]               [Page 5: Q&A]         [Pages 6–7: Findings & Diffs]
(Dashboard, Repo,         (SemanticChunker +         (Filter findings, inspect
 Code, Architecture)       VectorStore + Retriever    evidence, view unified
                           + QAEngine)                diff previews via DiffGenerator)
                                                             │
                                                             ▼
                                                    [Page 8: Sandbox Apply]
                                                             │
                                                (User reviews SAFE proposal)
                                                             │
                                              [Explicit Approval Checkbox Checked?]
                                                    │                   │
                                                  (No)                (Yes)
                                                    │                   ▼
                                            [Button Disabled]   [SandboxManager.execute_session()]
                                                                        │
                                                                        ├── Create temp sandbox copy
                                                                        ├── Run baseline tests
                                                                        ├── Apply patch diff
                                                                        ├── Run post-patch tests
                                                                        ├── Verify finding resolution
                                                                        ├── Verify target repo SHA-256
                                                                        └── Cleanup sandbox
                                                                        │
                                                                        ▼
                                                             [Page 9: Verification]
                                                        (Audit report & policy check)
                                                                        │
                                                                        ▼
                                                             [Page 10: Reports]
                                                        (Export JSON/patch artifacts)
```

---

## 7. Integration with Existing Engines

Each web page calls existing core modules directly without reimplementing any logic:

| Page | Core Modules & APIs Called |
|---|---|
| **Repository** | `ingestion.validator.validate_repository_path`<br>`ingestion.pipeline.IngestionPipeline.ingest`<br>`sandbox.copier.compute_directory_fingerprint` |
| **Code Understanding** | `analysis.analyzer.RepositoryAnalyzer.analyze_repository`<br>`analysis.models.RepositoryCodeIndex.get_classes`<br>`analysis.models.RepositoryCodeIndex.get_functions` |
| **Architecture** | `analysis.graph_builder.CodeGraphBuilder.build_graph`<br>`analysis.graph_models.CodeGraph.statistics`<br>`analysis.graph_models.CodeGraph.get_dependencies`<br>`analysis.graph_models.CodeGraph.get_dependents`<br>`analysis.graph_models.CodeGraph.get_callers`<br>`analysis.graph_models.CodeGraph.get_callees` |
| **Q&A** | `retrieval.chunker.SemanticChunker.chunk_repository`<br>`retrieval.vector_store.create_vector_store`<br>`retrieval.retriever.HybridRetriever`<br>`retrieval.context_builder.ContextBuilder`<br>`citations.validator.CitationValidator`<br>`retrieval.qa_engine.QAEngine.ask`<br>`llm.fake_provider.FakeLLMProvider`<br>`llm.openai_provider.OpenAIProvider` |
| **Findings** | `analysis.findings.context.AnalysisContext`<br>`analysis.findings.engine.AnalysisEngine.analyze`<br>`analysis.findings.models.AnalysisReport.filter_findings` |
| **Refactoring** | `refactoring.planner.RefactoringPlanner.plan`<br>`refactoring.generator.DiffGenerator.generate`<br>`refactoring.validator.DiffValidator.validate` |
| **Sandbox** | `sandbox.manager.SandboxManager.execute_session`<br>`sandbox.models.SafetyClassification.SAFE_AUTOMATIC_PROPOSAL` |
| **Verification** | `verification.engine.VerificationEngine.verify_repository`<br>`verification.engine.VerificationEngine.audit_sandbox_refactoring`<br>`verification.models.VerificationPolicy.strict`<br>`verification.models.VerificationPolicy.lenient` |
| **Reports** | `manifest.model_dump_json`<br>`code_index.export_json`<br>`code_graph.export_json`<br>`analysis_report.to_json`<br>`sandbox_report.to_json`<br>`verification_report.to_json` |

---

## 8. Safety and Approval Flow

### Immutability Guarantees
1. **Target Repository Read-Only:** All ingestion, AST parsing, graph construction, vector chunking, and static findings execution operate in strictly read-only mode.
2. **SHA-256 Fingerprint Tracking:** The target repository is fingerprinted via `compute_directory_fingerprint` before any pipeline execution and stored in `st.session_state["initial_sha256"]`.
3. **Post-Execution Immutability Verification:** Following any sandbox operation or verification audit, the target repository is fingerprinted again and compared against `initial_sha256`. If the hash differs, the session immediately raises an integrity violation error.

### Sandbox Isolation & Approval Barrier
1. **Approval Enforcement:** In `web/pages/sandbox.py`, the `Apply to Sandbox` button is disabled by default. It is only enabled when:
   - A proposal is selected.
   - The proposal's safety tier is strictly `SafetyClassification.SAFE_AUTOMATIC_PROPOSAL`.
   - The user explicitly checks the confirmation checkbox: `[x] I explicitly confirm and approve applying this refactoring patch to an isolated sandbox copy.`
2. **Rejection of Unsafe Tiers:** Proposals with `REVIEW_REQUIRED` or `UNSUPPORTED` display a prominent warning banner explaining why automatic sandbox application is blocked.
3. **No Direct Modification:** `SandboxManager` creates an isolated directory in `tempfile.gettempdir()`, copies repository contents, applies the diff via `SandboxPatcher`, runs tests via `SandboxTester`, verifies regression via `RegressionVerifier`, and deletes the sandbox directory via `SandboxCleanup` unless `keep_sandbox=True`.

### Secret Redaction & Path Traversal Guards
1. **Secret Redaction:** All reports, session outputs, error strings, and diff previews pass through `redact_secrets` regex filtering to prevent leakage of credentials, tokens, or environment keys.
2. **Path Traversal Protection:** All input paths are validated via `validate_repository_path`, which ensures existence, directory type, resolves symlinks, guards against system roots (`C:\`, `/`), and validates that paths remain within acceptable directory boundaries.

---

## 9. Testing Strategy

A comprehensive testing suite will be created in `tests/test_web/` to validate the new multi-page architecture without requiring live browser interactions:

### Test Suites to Add / Expand
1. **`tests/test_web/test_web_app.py` (Preserve & Extend):**
   - Retain all existing Phase 8.1 tests (`test_web_app_import`, `test_severity_badge_colors`, `test_safety_badge_colors`, `test_citation_formatting`, `test_path_validation_rejection`, `test_target_immutability_during_analysis`, `test_approval_boundary_enforced`, `test_no_secrets_in_web_app_source`, `test_file_record_metadata_access`).
   - Add tests verifying the entry-point router and page dispatching logic.
2. **`tests/test_web/test_web_pages.py` (New):**
   - Test clean import of each page module (`dashboard`, `repository`, `code_understanding`, `architecture`, `qa`, `findings`, `refactoring`, `sandbox`, `verification`, `reports`, `safety`).
   - Test that each page exposes a callable `render()` function.
   - Test rendering each page against a populated mock/fixture session state without exceptions.
   - Test empty-state handling (when no repository is loaded, pages render warning banners gracefully without crashing).
3. **`tests/test_web/test_web_state.py` (New):**
   - Test all getter and setter functions in `web/state.py`.
   - Test `reset_session_cache()` flushes all state keys.
   - Test that `is_repo_loaded()` returns correct boolean based on `manifest` presence.
4. **`tests/test_web/test_web_components.py` (New):**
   - Test badge rendering, color code lookups, diff formatting, and file size formatting helpers.
5. **`tests/test_web/test_api_regressions.py` (New - Explicit Regression Tests):**
   - Test 1: Verify `CodeGraph` uses `.statistics` attribute (and not `.compute_statistics()`).
   - Test 2: Verify `RepositoryCodeIndex` uses `.get_classes()` method (and not `.classes`).
   - Test 3: Verify `RepositoryCodeIndex` uses `.get_functions()` method (and not `.functions`).
6. **`tests/test_web/test_independence.py` (Preserve):**
   - Verify that no file in `src/` imports `streamlit` or `web`.
   - Verify that CLI `--help` and CLI commands function properly without Streamlit installed.

---

## 10. Documentation and Dependency Changes

### Documentation Updates
1. **`README.md`:**
   - Update the "Streamlit Web UI" section to describe the unified 11-page interface.
   - Document how to launch the multi-page application (`streamlit run web/app.py`).
   - Highlight the safety guarantees and sandbox isolation workflow.
2. **`docs/web_ui.md`:**
   - Overhaul to document the full 11-page architecture, session state schema, component layout, and approval lifecycle.
   - Provide screenshots/ASCII diagrams of the page flow.
3. **`docs/architecture.md`:**
   - Add a section explaining the Web Presentation Layer as a consumer of existing Phase 0–8 core engines.

### Dependency Changes
- **No new dependencies are required.**
- `requirements-web.txt` already specifies `streamlit>=1.30.0`.
- `pyproject.toml` already specifies `web = ["streamlit>=1.30.0"]` under `[project.optional-dependencies]`.
- Core dependencies (`click`/`typer`, `rich`, `openai`, `pydantic`, `pathspec`, `pytest`) remain untouched.

---

## 11. Known Bug Fixes and Regressions

The implementation will explicitly resolve the three known runtime defects identified during architectural inspection:

### Bug 1: `CodeGraph` Statistics Access
- **Incorrect:** `graph_stats = code_graph.compute_statistics()` (Line 334 of current `web/app.py`)
- **Root Cause:** `compute_statistics()` does not exist on `CodeGraph`. It is a private method (`_compute_statistics()`) on `CodeGraphBuilder`. The `CodeGraph` model stores statistics directly in its `.statistics` attribute (`GraphStatistics`).
- **Fix:** Update call to `graph_stats = code_graph.statistics` in `web/pages/architecture.py`.
- **Regression Test:** `test_codegraph_statistics_attribute_access` verifying `code_graph.statistics.total_nodes` works as expected.

### Bug 2: `RepositoryCodeIndex` Classes Access
- **Incorrect:** `len(code_index.classes)` (Line 339 of current `web/app.py`)
- **Root Cause:** `RepositoryCodeIndex` is a Pydantic model with fields `manifest`, `file_analyses`, and `summary`. It does not have a `.classes` field. Instead, it provides the method `code_index.get_classes() -> list[ClassInfo]`.
- **Fix:** Update call to `len(code_index.get_classes())` (or `code_index.summary.total_classes`) in `web/pages/architecture.py`, `dashboard.py`, and `code_understanding.py`.
- **Regression Test:** `test_code_index_get_classes_method_access` verifying `code_index.get_classes()` returns a list of `ClassInfo`.

### Bug 3: `RepositoryCodeIndex` Functions Access
- **Incorrect:** `len(code_index.functions)` (Line 340 of current `web/app.py`)
- **Root Cause:** `RepositoryCodeIndex` does not have a `.functions` field. It provides the method `code_index.get_functions(include_methods=False) -> list[FunctionInfo]`.
- **Fix:** Update call to `len(code_index.get_functions())` (or `code_index.summary.total_functions`) in `web/pages/architecture.py`, `dashboard.py`, and `code_understanding.py`.
- **Regression Test:** `test_code_index_get_functions_method_access` verifying `code_index.get_functions()` returns a list of `FunctionInfo`.

---

## 12. Implementation Sequence

The implementation will proceed in orderly, verified stages:

```
Step 1: Create State & Component Modules
        ├── web/state.py (Typed session-state accessors)
        └── web/components.py (Reusable badges, cards, formatters, diff view)
           │
           ▼
Step 2: Create Page Modules (web/pages/)
        ├── web/pages/__init__.py
        ├── web/pages/dashboard.py (Overview, health, metrics)
        ├── web/pages/repository.py (Files, languages, content viewer)
        ├── web/pages/code_understanding.py (AST classes, functions, imports, calls)
        ├── web/pages/architecture.py (CodeGraph, dependencies, cycles [FIX BUGS 1, 2, 3])
        ├── web/pages/qa.py (Q&A, hybrid retriever, citations, grounding)
        ├── web/pages/findings.py (Security, smells, patterns, filters)
        ├── web/pages/refactoring.py (Proposals, unified diffs, patch downloads)
        ├── web/pages/sandbox.py (Approval gate, isolated execution, regression tests)
        ├── web/pages/verification.py (Multi-check audit, policies, linting)
        ├── web/pages/reports.py (Artifact download center, JSON previews)
        └── web/pages/safety.py (SHA-256 monitor, invariants, settings)
           │
           ▼
Step 3: Refactor Entry Point (web/app.py)
        ├── Configure page layout & styling
        ├── Implement persistent sidebar (repo picker, load button, safety card)
        ├── Implement navigation router dispatching to active page
        └── Preserve backward-compatible public re-exports
           │
           ▼
Step 4: Implement Test Suites
        ├── tests/test_web/test_api_regressions.py (Bug 1, 2, 3 regression tests)
        ├── tests/test_web/test_web_state.py (State accessors & caching)
        ├── tests/test_web/test_web_components.py (UI components)
        └── tests/test_web/test_web_pages.py (Rendering tests for all 11 pages)
           │
           ▼
Step 5: Verification & Documentation
        ├── Run full test suite (`pytest tests/`)
        ├── Verify CLI commands remain functional without Streamlit
        ├── Verify repository immutability against fixtures
        └── Update docs/web_ui.md and README.md
```

---

## 13. Files to Create and Modify

### Files to Create
1. `web/state.py`: Centralized Streamlit session-state accessors and cache helpers.
2. `web/components.py`: Shared UI widgets, badges, formatters, and cards.
3. `web/pages/__init__.py`: Package marker for page modules.
4. `web/pages/dashboard.py`: Dashboard overview page.
5. `web/pages/repository.py`: Repository file structure and content inspector page.
6. `web/pages/code_understanding.py`: AST code understanding page.
7. `web/pages/architecture.py`: CodeGraph architecture and cycle detection page.
8. `web/pages/qa.py`: Codebase Q&A with citations page.
9. `web/pages/findings.py`: Static analysis findings page.
10. `web/pages/refactoring.py`: Refactoring plans and unified diffs page.
11. `web/pages/sandbox.py`: Sandbox apply and approval gate page.
12. `web/pages/verification.py`: Verification engine audit page.
13. `web/pages/reports.py`: Artifact export and download center page.
14. `web/pages/safety.py`: Safety monitoring and settings page.
15. `tests/test_web/test_api_regressions.py`: Regression tests for Bugs 1, 2, and 3.
16. `tests/test_web/test_web_state.py`: Unit tests for session state helpers.
17. `tests/test_web/test_web_components.py`: Unit tests for reusable UI components.
18. `tests/test_web/test_web_pages.py`: Unit tests for all 11 page modules.

### Files to Modify
1. `web/app.py`: Refactor from monolith into clean router/orchestrator; preserve backward-compatible exports.
2. `web/__init__.py`: Export key helpers for package-level access.
3. `README.md`: Update web application description and usage instructions.
4. `docs/web_ui.md`: Comprehensive user guide and architecture documentation.

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation Strategy |
|---|---|---|
| **Streamlit Re-run Overhead** | Streamlit re-executes the script on user interaction, which could trigger slow re-analysis or re-chunking. | Store pipeline outputs (`manifest`, `code_index`, `code_graph`, `analysis_report`, `refactoring_plan`) in `st.session_state`. Analysis runs **only** when the user explicitly clicks "Load & Analyze". |
| **Accidental In-Place Repo Modification** | Tampering with user code violates primary project invariant. | All patch applications are routed strictly through `SandboxManager`, which operates on temporary copies. Pre- and post-execution SHA-256 fingerprint checks abort on any hash mismatch. |
| **Bypassing Human Approval** | Applying changes without confirmation violates safety policy. | The "Apply" button is rendered in a disabled state until an explicit confirmation checkbox is toggled. The backend `SandboxManager` independently enforces `approved=True`. |
| **Breaking Core CLI Independence** | Adding web imports to `src/` breaks headless/CLI usage. | Enforce CI/pytest checks (`test_independence.py`) ensuring no `src/` module imports `streamlit` or `web`. |
| **API Desynchronization (e.g. Bugs 1–3)** | Presentation layer calls outdated or non-existent engine methods. | Add explicit regression tests in `test_api_regressions.py` validating that every API called by the UI exists on the underlying Pydantic model / class. |

---

## 15. Explicit Scope Boundaries

To maintain focus and adhere strictly to project phases:

### Explicitly Excluded (Out of Scope)
- **Phase 8.2 (Multi-language / Tree-sitter):** No tree-sitter integration or non-Python AST parsing.
- **Phase 8.3 (Interactive Visual Graphs):** No external graphviz, D3, or cytoscape JS visualization libraries (Mermaid text or Streamlit native tables/charts only).
- **Phase 8.4 (Git History Analysis):** No Git blame, commit parsing, or hotspot commit tracking.
- **Phase 8.5 (SARIF Output):** No SARIF schema generation or SARIF viewer integration.
- **Phase 8.6 (Plugin Architecture):** No dynamic rule loading from external files.
- **Phase 8.7 (JS/TS Support):** No JavaScript/TypeScript analyzers.
- **Phase 8.8 (Docker Sandboxing):** No containerized Docker execution (isolated temp directories only).
- **No Phase 9:** No autonomous agent looping, background daemon auto-refactoring, or automated PR creation.
