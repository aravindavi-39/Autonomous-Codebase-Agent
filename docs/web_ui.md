# Streamlit Web UI — Architecture & User Guide

Phase 8.1 introduces a browser-based developer dashboard for the Autonomous Codebase Understanding & Refactor Agent, providing a visual interface while preserving all safety, immutability, and approval invariants.

---

## 1. Architecture & Design Principles

```
┌─────────────────────────────────────────────────────────────┐
│                   STREAMLIT WEB DASHBOARD                   │
│                        (web/app.py)                         │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌─────────────────────────────┐
│       READ-ONLY OPS          │ │       MUTATING OPS          │
│ • Ingestion & Overview       │ │ • Change Proposals          │
│ • CodeGraph Relationships    │ │ • Unified Diff Previews     │
│ • Grounded Q&A + Citations   │ │ • Explicit Approval Gate    │
│ • Static Analysis & Findings │ │ • Ephemeral Tempdir Sandbox │
│ • Verification Engine Audit  │ │ • Subprocess Test Runner    │
└──────────────┬───────────────┘ └─────────────┬───────────────┘
               │                               │
               ▼                               ▼
    ┌────────────────────┐          ┌────────────────────┐
    │ Target Repository  │          │ Isolated Sandbox   │
    │ (Strictly Untouched│          │ (Created/Cleaned   │
    │  Verified SHA-256) │          │  Automatically)    │
    └────────────────────┘          └────────────────────┘
```

### Key Design Tenets
1. **Zero Core Coupling:** `web/app.py` imports and orchestrates existing Python APIs from `src/`. No core engine or CLI module imports `web` or `streamlit`.
2. **Optional Dependency:** Streamlit is defined under `[project.optional-dependencies] web` and in `requirements-web.txt`. The CLI and test suite run without Streamlit installed.
3. **Strict Target Immutability:** The target repository is fingerprinted (SHA-256) before and after all operations. Analysis and Q&A never write to the repository.
4. **Human Approval Boundary:** The web UI enforces an explicit checkbox confirmation before applying any patch. Modifications occur exclusively inside an isolated temporary sandbox (`tempfile.mkdtemp()`).
5. **Secret Redaction:** No environment variables, tokens, credentials, or API keys are ever displayed in UI components or logs.

---

## 2. Installation & Launch

### Install Optional Dependencies
```bash
pip install -r requirements-web.txt
# or via pip optional dependencies
pip install ".[web]"
```

### Launch the Application
```bash
streamlit run web/app.py
```

To run in headless or custom port mode:
```bash
streamlit run web/app.py --server.headless true --server.port 8501
```

---

## 3. UI Walkthrough

### 📁 Sidebar: Repository Selection & Settings
- **Repository Selector:** Choose from preset repositories (such as `tests/fixtures/sandbox_test_repo`) or enter any valid local repository path.
- **Path Validation:** Validates directory existence and guards against path traversal or system root access.
- **Model Settings:** Toggle between offline mock mode (`FakeLLMProvider`) and live OpenAI API mode (`OpenAIProvider`). Adjust chunk limits (`top-k`) and context budgets.
- **Safety Status:** Displays the active target repository SHA-256 fingerprint and real-time safety invariants.

### 📊 Tab 1: Repository Overview
- Displays high-level repository statistics: total files, directories, lines of code, test file count, configuration files, and documentation.
- Visualizes detected programming languages and directory structure.

### 🕸️ Tab 2: CodeGraph & Architecture
- Visualizes codebase AST metrics: classes, functions, and cross-file method calls.
- Summarizes inter-module relationships (`IMPORTS`, `DEFINES`, `CALLS`, `CONTAINS`, `TESTS`, `DEPENDS_ON`).
- Displays dependency hotspots and circular dependency checks (green checkmark for acyclic graphs, red alerts for cycles).

### 💬 Tab 3: Ask the Codebase (Q&A)
- Natural language query interface powered by hybrid retrieval (semantic ChromaDB embeddings + structural CodeGraph traversal).
- Displays grounded synthesis and verified source citations (`📄 file:start-end (entity)`).
- Grounding status badge verifies whether retrieved evidence is sufficient, preventing hallucinated answers.

### 🔍 Tab 4: Findings & Smells
- Displays findings categorized into **Security**, **Code Smells**, and **Coding Patterns**.
- Filterable by Category and Severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
- Each finding includes code evidence, line bounds, entity name, an explanation of why the issue matters, and an actionable recommendation.

### 🛠️ Tab 5: Refactoring Plan & Unified Diffs
- Summarizes available refactoring transformations and safety tiers (`SAFE_AUTOMATIC_PROPOSAL`, `REVIEW_REQUIRED`, `UNSUPPORTED`).
- Renders deterministic, syntax-highlighted unified diff previews for proposed changes.

### 🧪 Tab 6: Sandbox Application & Verification
- **Approval Gate:** Requires user to review the proposal and check the mandatory confirmation box:  
  `[x] I explicitly confirm and approve applying this refactoring patch to an isolated sandbox copy.`
- **Isolated Sandbox Execution:** Applies the patch in an isolated temporary directory, runs baseline and post-patch test suites, and reports the regression verdict (`PASS` / `FAIL`).
- **Verification Engine Audit:** Audits unit tests, AST linter syntax/whitespace/line-length rules, evidence-based target finding resolution, and verifies the original repository SHA-256 fingerprint remains 100% untouched.
