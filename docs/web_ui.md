# Streamlit Web UI — Architecture & User Guide

The Streamlit Web UI provides a comprehensive browser-based developer dashboard for the Autonomous Codebase Understanding & Refactor Agent, exposing the full capabilities of **Phases 0 through 8** while strictly enforcing safety, immutability, and human-approval invariants.

---

## 1. Architecture & Design Principles

```
┌─────────────────────────────────────────────────────────────┐
│                 STREAMLIT WEB APPLICATION                   │
│                        (web/app.py)                         │
│                                                             │
│   web/state.py         web/components.py      web/pages/    │
│  (Session Cache)      (Badges & Cards)       (11 Views)     │
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
1. **Zero Core Coupling:** The web layer (`web/`) is strictly a presentation layer. Core engines (`src/`) never import Streamlit or any web modules.
2. **Modular Multi-Page Structure:**
   - `web/app.py`: Application entry point, layout, and page routing.
   - `web/state.py`: Centralized, typed session-state accessors and cache management.
   - `web/components.py`: Reusable UI elements, badges, formatters, and safety banners.
   - `web/pages/*.py`: Dedicated presentation controllers for each of the 11 functional views.
3. **Optional Dependency:** Streamlit is defined under `[project.optional-dependencies] web` and `requirements-web.txt`. The CLI and test suite run without Streamlit installed.
4. **Strict Target Immutability:** The target repository is fingerprinted (SHA-256) before and after all operations. Analysis, AST indexing, and Q&A never write to the repository.
5. **Human Approval Boundary:** The web UI enforces an explicit checkbox confirmation before applying any patch. Modifications occur exclusively inside an isolated temporary sandbox (`tempfile.mkdtemp()`).
6. **Secret Redaction:** No environment variables, tokens, credentials, or API keys are ever displayed in UI components or logs.

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

## 3. The 11 Unified Pages

### 1. 📊 Dashboard (`web/pages/dashboard.py`)
- Repository metadata, absolute path, and SHA-256 fingerprint.
- Top-level metrics: files, lines of code, classes, functions, findings, and proposals.
- Real-time pipeline phase execution indicators (Ingestion, AST, Graph, Findings, Refactoring, Sandbox, Verification).

### 2. 📁 Repository & Ingestion (`web/pages/repository.py`)
- File structure metrics: total files, directories, size, test files, and config files.
- Discovered file table with keyword search and language filters.
- Interactive file content viewer rendering syntax-highlighted source code with line counts and file sizes.

### 3. 🧠 Code Understanding (`web/pages/code_understanding.py`)
- AST analysis metrics: classes, standalone functions, methods, imports, and cross-file invocations.
- Interactive explorers for classes (bases, docstrings, methods), functions (annotations, async flags, calls), imports (stdlib/third-party/local), and call graphs.

### 4. 🕸️ Architecture & Graph (`web/pages/architecture.py`)
- CodeGraph node, edge, class, and function metrics.
- Relationship type breakdown table (`IMPORTS`, `DEFINES`, `CALLS`, `INHERITS`, etc.).
- Circular dependency detection with highlighted cycle chains.
- Hotspot module tracking and interactive entity dependency/dependent explorer.

### 5. 💬 Codebase Q&A (`web/pages/qa.py`)
- Grounded question-answering powered by hybrid semantic vector and structural graph retrieval.
- Verified source citations formatted as `📄 file:start-end (entity)`.
- Groundedness verification indicator.
- Persistent session Q&A interaction history.

### 6. 🔍 Findings & Security (`web/pages/findings.py`)
- Static code analysis findings categorized into **Security**, **Code Smells**, and **Coding Patterns**.
- Filterable by Category and Severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
- Comprehensive cards with verbatim code evidence snippets, rationale, and remediation recommendations.
- Downloadable JSON findings report.

### 7. 🛠️ Refactoring & Diffs (`web/pages/refactoring.py`)
- Prioritized refactoring plans with safety tiers (`SAFE_AUTOMATIC_PROPOSAL`, `REVIEW_REQUIRED`, `UNSUPPORTED`).
- Syntax-highlighted unified diff previews generated deterministically via `DiffGenerator`.
- Download individual `.patch` files or all diffs combined.

### 8. 🧪 Sandbox Apply (`web/pages/sandbox.py`)
- Strict human approval gate:
  `[x] I explicitly confirm and approve applying this refactoring patch to an isolated sandbox copy.`
- Applies `SAFE_AUTOMATIC_PROPOSAL` changes exclusively inside ephemeral temporary sandboxes.
- Baseline vs. post-patch subprocess test comparisons and regression verdict (`PASS` / `FAIL`).
- Automatic sandbox cleanup and target repository immutability verification.

### 9. 📋 Verification Engine (`web/pages/verification.py`)
- Standalone multi-check verification audit.
- Configurable policies (`STRICT` vs. `LENIENT`), test execution toggles, and AST linter checks.
- Detailed check status table, lint violation listings, and finding delta resolution assessment.

### 10. 📑 Reports & Exports (`web/pages/reports.py`)
- Centralized export center for all generated artifacts.
- One-click JSON downloads: Manifest, Code Index, CodeGraph, Analysis Findings, Refactoring Plan, Sandbox Report, and Verification Report.
- Interactive in-browser JSON preview with copy support.

### 11. 🛡️ Safety & Settings (`web/pages/safety.py`)
- Real-time target repository SHA-256 fingerprint monitor and live immutability verification.
- Enforced project safety invariants checklist.
- LLM provider configuration (Offline/Mock vs. live OpenAI) with session-only in-memory API key handling.
- Session cache flush and reload controls.
