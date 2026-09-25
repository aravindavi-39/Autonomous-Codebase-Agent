# Autonomous Codebase Understanding & Refactor Agent — Project Plan

> **Version:** 1.0  
> **Date:** 2026-09-24  
> **Status:** Draft — Awaiting Approval

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [A — Overall System Architecture](#2-a--overall-system-architecture)
3. [B — Recommended Technology Stack](#3-b--recommended-technology-stack)
4. [C — Project Folder Structure](#4-c--project-folder-structure)
5. [D — Major Modules / Components](#5-d--major-modulescomponents)
6. [E — Data Flow](#6-e--data-flow)
7. [F — Agent Workflow](#7-f--agent-workflow)
8. [G — Security & Safety Mechanisms](#8-g--security--safety-mechanisms)
9. [H — Step-by-Step Implementation Plan](#9-h--step-by-step-implementation-plan)
10. [Appendix — Glossary & References](#10-appendix--glossary--references)

---

## 1. Project Overview

### 1.1 Problem Statement

Developers frequently inherit, onboard onto, or audit codebases they did not write.
Understanding the architecture, finding code smells, spotting security issues, and
safely refactoring such projects is time-consuming and error-prone.

### 1.2 Solution

An **AI-powered agent** that can:

| # | Capability | Req |
|---|-----------|-----|
| 1 | Accept a GitHub URL or local path | R1 |
| 2 | Ingest repository structure, source code & docs | R2 |
| 3 | Parse files, classes, functions, imports & dependencies | R3 |
| 4 | Answer architecture / codebase questions | R4 |
| 5 | Provide file + line-number citations | R5 |
| 6 | Detect code smells | R6 |
| 7 | Detect common security issues | R7 |
| 8 | Detect outdated coding / dependency patterns | R8 |
| 9 | Explain issues in junior-friendly language | R9 |
| 10 | Propose a refactoring plan | R10 |
| 11 | Generate code diffs before changes | R11 |
| 12 | Run tests & static analysis | R12 |
| 13 | Report pass/fail verification results | R13 |
| 14 | **Never** modify the original repo without approval | R14 |

### 1.3 Design Principles

- **Safety first** — all mutations happen on an isolated copy.
- **Simple core, extensible shell** — a college student can build the MVP; an advanced developer can extend it with plugins.
- **Transparency** — every answer carries citations; every change shows a diff.

---

## 2. A — Overall System Architecture

### 2.1 High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                            │
│                  (CLI  /  Streamlit Web UI)                       │
└──────────────┬───────────────────────────────┬───────────────────┘
               │  user commands / questions     │  results / diffs
               ▼                               ▲
┌──────────────────────────────────────────────────────────────────┐
│                     AGENT ORCHESTRATOR                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │  Ingestion │ │  Analysis  │ │ Refactoring│ │ Verification │  │
│  │  Pipeline  │ │  Engine    │ │  Engine    │ │   Engine     │  │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬───────┘  │
│        │              │              │               │           │
│        ▼              ▼              ▼               ▼           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 SHARED SERVICES LAYER                       │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │ │
│  │  │ Code     │ │ LLM      │ │ Citation │ │ Sandbox       │  │ │
│  │  │ Index /  │ │ Gateway  │ │ Tracker  │ │ Manager       │  │ │
│  │  │ VectorDB │ │          │ │          │ │ (git worktree) │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
               │                               │
               ▼                               ▼
    ┌────────────────┐               ┌────────────────┐
    │  Target Repo   │               │  Isolated Copy  │
    │  (read-only)   │               │  (mutations OK) │
    └────────────────┘               └────────────────┘
```

### 2.2 Layer Descriptions

| Layer | Responsibility |
|-------|---------------|
| **User Interface** | CLI and optional web dashboard; collects input, displays results |
| **Agent Orchestrator** | Coordinates the four engines; manages conversation state |
| **Ingestion Pipeline** | Clones/copies repo → parses AST → builds code index |
| **Analysis Engine** | Code smells, security scan, dependency audit, Q&A |
| **Refactoring Engine** | Generates refactor plans & unified diffs |
| **Verification Engine** | Runs tests and linters on the isolated copy |
| **Shared Services** | Code index (vector store), LLM gateway, citation tracker, sandbox |

---

## 3. B — Recommended Technology Stack

### 3.1 Core Stack

| Concern | Technology | Rationale |
|---------|-----------|-----------|
| **Language** | Python 3.11+ | Rich ecosystem for AI/ML, AST parsing, CLI tooling |
| **LLM Provider** | OpenAI API (GPT-4o / GPT-4o-mini) via `openai` SDK | Widely available; easy API key setup for students |
| **Embeddings** | `sentence-transformers` (all-MiniLM-L6-v2) or OpenAI `text-embedding-3-small` | Lightweight local embeddings, or API-based |
| **Vector Store** | ChromaDB (local, file-backed) | Zero-config, pip-installable, perfect for college projects |
| **AST Parsing** | `ast` (Python), `tree-sitter` (multi-language) | `ast` for MVP (Python-only); `tree-sitter` for extension |
| **Static Analysis** | `pylint`, `flake8`, `bandit` (security) | Industry-standard, well-documented |
| **Dependency Audit** | `pip-audit`, `safety` | Detect known CVEs in dependencies |
| **Diff Generation** | Python `difflib` / `unidiff` | Standard library / lightweight |
| **Test Runner** | `pytest` (subprocess invocation) | Most common Python test framework |
| **Git Operations** | `gitpython` | Clone, branch, worktree management |
| **CLI Framework** | `typer` + `rich` | Beautiful CLI with minimal code |
| **Web UI (optional)** | Streamlit | Rapid prototyping; single-file apps |
| **Config** | `pydantic-settings` + `.env` | Type-safe configuration |

### 3.2 Development & Quality

| Concern | Technology |
|---------|-----------|
| Dependency management | `pip` + `requirements.txt` (MVP), `poetry` (stretch) |
| Formatting | `black`, `isort` |
| Type checking | `mypy` |
| Testing | `pytest` + `pytest-cov` |
| Pre-commit hooks | `pre-commit` |

---

## 4. C — Project Folder Structure

```
Autonomous-Codebase-Agent/
│
├── PROJECT_PLAN.md              ← You are here
├── README.md                    ← User-facing documentation
├── requirements.txt             ← Python dependencies
├── .env.example                 ← Template for API keys / config
├── .gitignore
├── setup.py                     ← Package setup (optional)
│
├── config/
│   └── settings.py              ← Pydantic settings, env loading
│
├── src/
│   ├── __init__.py
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py              ← Typer CLI entry point
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── repo_loader.py       ← Clone / copy repo
│   │   ├── file_parser.py       ← Read & classify files
│   │   ├── ast_parser.py        ← AST extraction (classes, funcs, imports)
│   │   ├── dependency_parser.py ← requirements.txt / pyproject.toml parser
│   │   └── indexer.py           ← Build vector index (ChromaDB)
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── qa_engine.py         ← RAG-based Q&A with citations
│   │   ├── code_smells.py       ← Code smell detector
│   │   ├── security_scanner.py  ← Security issue detector (bandit wrapper)
│   │   ├── dependency_audit.py  ← Outdated / vulnerable dep checker
│   │   └── explainer.py         ← Junior-friendly explanation generator
│   │
│   ├── refactoring/
│   │   ├── __init__.py
│   │   ├── planner.py           ← Generate refactoring plan
│   │   ├── diff_generator.py    ← Produce unified diffs
│   │   └── applier.py           ← Apply diffs to sandbox copy
│   │
│   ├── verification/
│   │   ├── __init__.py
│   │   ├── test_runner.py       ← Run pytest in subprocess
│   │   ├── lint_runner.py       ← Run flake8/pylint in subprocess
│   │   └── reporter.py          ← Aggregate & format results
│   │
│   ├── sandbox/
│   │   ├── __init__.py
│   │   └── manager.py           ← Isolated copy management (git worktree / tempdir)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── gateway.py           ← Unified LLM call interface
│   │   ├── prompts.py           ← Prompt templates
│   │   └── embeddings.py        ← Embedding generation
│   │
│   ├── citations/
│   │   ├── __init__.py
│   │   └── tracker.py           ← Map answers → file:line references
│   │
│   └── utils/
│       ├── __init__.py
│       ├── git_utils.py         ← Git helper functions
│       ├── file_utils.py        ← File I/O helpers
│       └── logger.py            ← Structured logging setup
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              ← Shared fixtures
│   ├── test_ingestion/
│   ├── test_analysis/
│   ├── test_refactoring/
│   ├── test_verification/
│   └── test_sandbox/
│
├── web/                         ← Optional Streamlit UI
│   └── app.py
│
└── docs/
    ├── architecture.md
    └── user_guide.md
```

---

## 5. D — Major Modules / Components

### 5.1 Ingestion Pipeline

```
GitHub URL / Local Path
        │
        ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  repo_loader  │───▶│  file_parser  │───▶│  ast_parser   │
│  (clone/copy) │    │ (read & filter│    │ (extract      │
│               │    │  by extension)│    │  symbols)     │
└───────────────┘    └───────────────┘    └───────┬───────┘
                                                  │
                     ┌───────────────┐            │
                     │   indexer     │◀───────────┘
                     │ (chunk code → │
                     │  embed →      │
                     │  store in     │
                     │  ChromaDB)    │
                     └───────────────┘
```

**Key responsibilities:**

| Module | What it does |
|--------|-------------|
| `repo_loader` | Clones a GitHub repo (via `gitpython`) or validates a local path; creates the sandbox copy |
| `file_parser` | Walks the directory tree; filters out binaries, `node_modules`, `.git`, etc.; classifies files by language |
| `ast_parser` | Uses Python's `ast` module (or `tree-sitter` for multi-lang) to extract classes, functions, imports, decorators, docstrings |
| `dependency_parser` | Parses `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` to list dependencies + versions |
| `indexer` | Splits source files into overlapping chunks (with metadata: file path, line range, symbol names), generates embeddings, stores in ChromaDB |

### 5.2 Analysis Engine

| Module | What it does | Maps to Req |
|--------|-------------|-------------|
| `qa_engine` | Retrieval-Augmented Generation: retrieves relevant chunks from ChromaDB, sends them + user question to the LLM, returns answer with citations | R4, R5 |
| `code_smells` | Runs heuristics + LLM analysis to detect: long functions, god classes, duplicate code, deep nesting, unused imports | R6 |
| `security_scanner` | Wraps `bandit` for static security analysis; parses output into structured findings | R7 |
| `dependency_audit` | Runs `pip-audit` / `safety check` to find known CVEs; compares installed versions against latest PyPI versions | R8 |
| `explainer` | Takes any finding (smell, vulnerability, outdated dep) and generates a junior-developer-friendly explanation using the LLM | R9 |

### 5.3 Refactoring Engine

| Module | What it does | Maps to Req |
|--------|-------------|-------------|
| `planner` | Given analysis findings, uses the LLM to generate a prioritized refactoring plan with rationale | R10 |
| `diff_generator` | For each refactoring step, generates a unified diff showing exactly what will change | R11 |
| `applier` | Applies approved diffs to the **sandbox copy only**; never touches the original | R14 |

### 5.4 Verification Engine

| Module | What it does | Maps to Req |
|--------|-------------|-------------|
| `test_runner` | Runs `pytest` inside the sandbox via subprocess; captures exit code + output | R12 |
| `lint_runner` | Runs `flake8` / `pylint` inside the sandbox; captures findings | R12 |
| `reporter` | Aggregates test + lint results; produces a pass/fail summary with details | R13 |

### 5.5 Shared Services

| Module | What it does |
|--------|-------------|
| `llm/gateway` | Single interface for all LLM calls; handles retries, rate limiting, token counting, model selection |
| `llm/prompts` | Jinja2 or f-string prompt templates for each use case (Q&A, smell detection, explanation, refactoring) |
| `llm/embeddings` | Generates embeddings via local model or API |
| `citations/tracker` | Maintains a mapping from each answer/finding to `(file_path, start_line, end_line)` tuples |
| `sandbox/manager` | Creates and manages an isolated working copy using `git worktree` or `tempfile.mkdtemp()` |

---

## 6. E — Data Flow

### 6.1 End-to-End Data Flow Diagram

```
                                    USER
                                     │
                          ┌──────────┴──────────┐
                          │   1. Provide repo    │
                          │      URL / path      │
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  2. INGEST           │
                          │  • Clone / copy      │
                          │  • Parse files        │
                          │  • Extract AST        │
                          │  • Build vector index │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  CODE INDEX          │
                          │  (ChromaDB)          │
                          │  + Symbol Table      │
                          │  + File Metadata     │
                          └──────────┬──────────┘
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                   ▼                   ▼
       ┌─────────────┐    ┌─────────────────┐  ┌──────────────┐
       │ 3. Q&A      │    │ 4. ANALYSIS     │  │ 5. REFACTOR  │
       │ (RAG +      │    │ • Code smells   │  │ • Plan       │
       │  Citations)  │    │ • Security      │  │ • Diff       │
       │              │    │ • Dependencies  │  │ • Apply      │
       └──────┬──────┘    └───────┬─────────┘  └──────┬───────┘
              │                   │                    │
              ▼                   ▼                    ▼
       ┌─────────────────────────────────────────────────────┐
       │           6. RESULTS  (with citations)              │
       │  • Answers with file:line references                │
       │  • Findings explained for junior developers         │
       │  • Unified diffs for proposed changes               │
       └────────────────────────┬────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  7. USER APPROVAL      │
                    │  "Apply this diff?"    │
                    └───────────┬───────────┘
                                │ yes
                    ┌───────────▼───────────┐
                    │  8. APPLY TO SANDBOX   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  9. VERIFY             │
                    │  • Run tests           │
                    │  • Run linters         │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 10. REPORT             │
                    │  "Tests passed ✓"      │
                    │  "2 lint warnings ⚠"   │
                    └───────────────────────┘
```

### 6.2 Data Artifacts

| Artifact | Format | Storage |
|----------|--------|---------|
| Cloned repository | Directory tree | Temp directory / workspace |
| Parsed file records | `FileRecord` dataclass: path, language, size, line count | In-memory |
| AST symbols | `Symbol` dataclass: name, kind, file, start_line, end_line, docstring | In-memory + ChromaDB metadata |
| Code chunks | Text chunks (300-500 tokens) with overlap | ChromaDB documents |
| Embeddings | Float vectors (384-dim or 1536-dim) | ChromaDB |
| Analysis findings | `Finding` dataclass: type, severity, file, line, description, explanation | In-memory → JSON/Markdown |
| Refactoring plan | Markdown document | File on disk |
| Diffs | Unified diff strings | File on disk |
| Verification results | `VerificationReport` dataclass: passed, test_output, lint_output | In-memory → JSON/Markdown |

---

## 7. F — Agent Workflow

### 7.1 Conversation-Driven Workflow

The agent operates in a **REPL-style conversation loop**:

```
┌─────────────────────────────────────────────────────────┐
│                    AGENT LOOP                            │
│                                                          │
│  1. Wait for user command                                │
│  2. Route command to appropriate engine:                 │
│     ┌──────────────────────────────────────────┐        │
│     │  "load <url>"         → Ingestion        │        │
│     │  "ask <question>"     → QA Engine         │        │
│     │  "analyze"            → Analysis Engine   │        │
│     │  "scan security"      → Security Scanner  │        │
│     │  "check deps"         → Dependency Audit  │        │
│     │  "explain <finding>"  → Explainer          │        │
│     │  "plan refactor"      → Refactoring Plan  │        │
│     │  "show diff <item>"   → Diff Generator    │        │
│     │  "apply <diff>"       → Applier (sandbox) │        │
│     │  "verify"             → Verification      │        │
│     │  "report"             → Reporter          │        │
│     └──────────────────────────────────────────┘        │
│  3. Execute engine with sandbox isolation                │
│  4. Attach citations to output                           │
│  5. Display results to user                              │
│  6. Go to step 1                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Detailed Workflow — Full Analysis & Refactor Cycle

```
Step 1: LOAD
  Input:  GitHub URL or local path
  Action: Clone → create sandbox → parse → index
  Output: "Repository loaded. 142 files indexed. Ready for questions."

Step 2: EXPLORE (interactive)
  Input:  "What does this project do?"
  Action: RAG retrieval → LLM synthesis → attach citations
  Output: "This is a Flask web app that ... [src/app.py:1-30] [README.md:5-20]"

Step 3: ANALYZE
  Input:  "analyze" command
  Action: Run code smell detection + security scan + dependency audit in parallel
  Output: Structured findings with severity levels

Step 4: EXPLAIN
  Input:  "explain finding #3"
  Action: LLM generates junior-friendly explanation
  Output: "This function has 'God Class' smell because ... Here's why that's a problem ..."

Step 5: PLAN
  Input:  "plan refactor"
  Action: LLM reviews all findings → generates prioritized plan
  Output: Numbered refactoring steps with rationale

Step 6: PREVIEW
  Input:  "show diff for step 1"
  Action: LLM generates code changes → diff_generator creates unified diff
  Output: Colored diff output in terminal

Step 7: APPROVE & APPLY
  Input:  "apply" (user approval)
  Action: Apply diff to sandbox copy ONLY
  Output: "Changes applied to sandbox. Original repository untouched."

Step 8: VERIFY
  Input:  "verify" command
  Action: Run pytest + flake8 in sandbox
  Output: "✓ 45/45 tests passed. ⚠ 2 new lint warnings (style only)."

Step 9: EXPORT (optional)
  Input:  "export patch"
  Action: Generate a .patch file from sandbox
  Output: Path to .patch file user can review & apply manually
```

---

## 8. G — Security & Safety Mechanisms

### 8.1 Core Safety Principle

> **The agent NEVER modifies the original repository.**  
> All mutations happen on an isolated sandbox copy.

### 8.2 Safety Architecture

```
┌────────────────────────────────────────────────┐
│               SAFETY LAYERS                     │
│                                                  │
│  Layer 1: ISOLATION                              │
│  ├─ Original repo mounted read-only             │
│  ├─ Sandbox copy in temp directory               │
│  └─ Git worktree for branch isolation            │
│                                                  │
│  Layer 2: APPROVAL GATE                          │
│  ├─ Every diff requires explicit user approval   │
│  ├─ "apply" command requires confirmation         │
│  └─ Batch changes show full diff before apply    │
│                                                  │
│  Layer 3: VERIFICATION                           │
│  ├─ Tests must run after every applied change    │
│  ├─ Lint check after every applied change        │
│  └─ Rollback available if tests fail             │
│                                                  │
│  Layer 4: AUDIT TRAIL                            │
│  ├─ Every action logged with timestamp            │
│  ├─ Every LLM call logged (prompt + response)    │
│  └─ Change history maintained as git commits     │
│                                                  │
│  Layer 5: INPUT VALIDATION                       │
│  ├─ Sanitize GitHub URLs                         │
│  ├─ Validate local paths exist                   │
│  ├─ Reject repos above configurable size limit   │
│  └─ Filter out binary / sensitive files           │
└────────────────────────────────────────────────┘
```

### 8.3 Specific Safety Mechanisms

| Mechanism | Implementation | Protects Against |
|-----------|---------------|-----------------|
| **Read-only mount** | `os.open()` with `O_RDONLY`; refuse writes to original path | Accidental modification of original repo |
| **Sandbox directory** | `tempfile.mkdtemp()` or `git worktree add` | Mutations leaking to original |
| **Approval prompt** | CLI confirmation: `"Apply changes? [y/N]"` | Unintended code changes |
| **Diff preview** | Always show full diff before apply | Blind/opaque changes |
| **Test gate** | Auto-run tests after applying changes | Introducing regressions |
| **Rollback** | `git checkout -- .` in sandbox | Recovering from bad changes |
| **Size limits** | Config: `MAX_REPO_SIZE_MB = 500`, `MAX_FILE_SIZE_KB = 500` | DoS / memory exhaustion |
| **File filters** | Skip `.git/`, `node_modules/`, `*.pyc`, `*.exe`, `*.bin`, secrets patterns | Indexing irrelevant / dangerous content |
| **API key protection** | `.env` file not committed; `python-dotenv` for loading | Leaking credentials |
| **Rate limiting** | Configurable max LLM calls per session | Runaway API costs |
| **Subprocess sandboxing** | `subprocess.run()` with timeout, restricted env | Malicious test/lint commands |

### 8.4 Sensitive File Handling

The agent will scan for and **exclude** from indexing:

- `.env`, `.env.*` files
- Files matching patterns: `*secret*`, `*password*`, `*credential*`, `*token*`
- Private keys: `*.pem`, `*.key`, `id_rsa*`
- Anything listed in `.gitignore`

---

## 9. H — Step-by-Step Implementation Plan

### Phase 0 — Project Bootstrap (Day 1)

| Step | Task | Deliverable |
|------|------|-------------|
| 0.1 | Create project directory structure | Folder tree as specified in §4 |
| 0.2 | Initialize Git repository | `.gitignore`, initial commit |
| 0.3 | Create `requirements.txt` with core dependencies | Dependency file |
| 0.4 | Set up `config/settings.py` with Pydantic | Configuration module |
| 0.5 | Set up `src/utils/logger.py` | Structured logging |
| 0.6 | Create `.env.example` | Template for API keys |

### Phase 1 — Ingestion Pipeline (Days 2–4)

| Step | Task | Deliverable | Tests |
|------|------|-------------|-------|
| 1.1 | `repo_loader.py` — clone GitHub repo via `gitpython` | Working clone from URL | `test_clone_public_repo` |
| 1.2 | `repo_loader.py` — accept local path, validate it exists | Local path validation | `test_local_path_validation` |
| 1.3 | `file_parser.py` — walk directory, filter files, classify by language | List of `FileRecord` objects | `test_file_discovery` |
| 1.4 | `ast_parser.py` — extract Python classes, functions, imports using `ast` | List of `Symbol` objects | `test_ast_extraction` |
| 1.5 | `dependency_parser.py` — parse `requirements.txt` | List of `(package, version)` | `test_requirements_parsing` |
| 1.6 | `indexer.py` — chunk files, generate embeddings, store in ChromaDB | Populated ChromaDB collection | `test_indexing_and_retrieval` |
| 1.7 | `sandbox/manager.py` — create isolated working copy | Temp directory with repo copy | `test_sandbox_creation` |

### Phase 2 — LLM Integration & Q&A (Days 5–7)

| Step | Task | Deliverable | Tests |
|------|------|-------------|-------|
| 2.1 | `llm/gateway.py` — unified LLM call interface with retries | `llm_call(prompt, model)` function | `test_llm_gateway_mock` |
| 2.2 | `llm/embeddings.py` — embedding generation | `embed(text)` function | `test_embedding_dimensions` |
| 2.3 | `llm/prompts.py` — define prompt templates for Q&A | Template strings | Unit tests for template rendering |
| 2.4 | `citations/tracker.py` — map retrieved chunks to file:line | `Citation` dataclass | `test_citation_mapping` |
| 2.5 | `analysis/qa_engine.py` — RAG pipeline: query → retrieve → generate → cite | End-to-end Q&A with citations | `test_qa_returns_citations` |

### Phase 3 — Analysis Engine (Days 8–11)

| Step | Task | Deliverable | Tests |
|------|------|-------------|-------|
| 3.1 | `analysis/code_smells.py` — detect long functions (>50 lines) | List of smell findings | `test_long_function_detection` |
| 3.2 | `analysis/code_smells.py` — detect deep nesting (>4 levels) | Additional findings | `test_deep_nesting_detection` |
| 3.3 | `analysis/code_smells.py` — detect unused imports | Additional findings | `test_unused_import_detection` |
| 3.4 | `analysis/code_smells.py` — LLM-assisted smell detection for complex patterns | Additional findings | `test_llm_smell_detection` |
| 3.5 | `analysis/security_scanner.py` — wrap `bandit`, parse JSON output | Security findings | `test_bandit_wrapper` |
| 3.6 | `analysis/dependency_audit.py` — wrap `pip-audit`, detect outdated deps | Dependency findings | `test_dependency_audit` |
| 3.7 | `analysis/explainer.py` — generate junior-friendly explanations via LLM | Explanation strings | `test_explanation_readability` |

### Phase 4 — Refactoring Engine (Days 12–14)

| Step | Task | Deliverable | Tests |
|------|------|-------------|-------|
| 4.1 | `refactoring/planner.py` — generate prioritized refactoring plan | Markdown plan document | `test_plan_generation` |
| 4.2 | `refactoring/diff_generator.py` — produce unified diffs via LLM | Diff strings | `test_diff_format` |
| 4.3 | `refactoring/applier.py` — apply diffs to sandbox copy safely | Modified sandbox files | `test_diff_application` |
| 4.4 | Approval gate — require explicit user confirmation before apply | Confirmation flow | `test_approval_gate_blocks` |

### Phase 5 — Verification Engine (Days 15–16)

| Step | Task | Deliverable | Tests |
|------|------|-------------|-------|
| 5.1 | `verification/test_runner.py` — run pytest in sandbox subprocess | Test results (pass/fail/output) | `test_pytest_runner` |
| 5.2 | `verification/lint_runner.py` — run flake8 in sandbox subprocess | Lint results | `test_flake8_runner` |
| 5.3 | `verification/reporter.py` — aggregate results, format report | Verification report | `test_report_format` |

### Phase 6 — CLI Interface (Days 17–18)

| Step | Task | Deliverable | Tests |
|------|------|-------------|-------|
| 6.1 | `cli/main.py` — define `load`, `ask`, `analyze`, `explain` commands | Working CLI commands | Manual testing |
| 6.2 | `cli/main.py` — define `plan`, `diff`, `apply`, `verify` commands | Working CLI commands | Manual testing |
| 6.3 | Rich output formatting — colored diffs, tables, progress bars | Polished CLI output | Manual testing |
| 6.4 | Error handling — graceful failures with helpful messages | User-friendly errors | `test_error_messages` |

### Phase 7 — Integration & Polish (Days 19–21)

| Step | Task | Deliverable | Tests |
|------|------|-------------|-------|
| 7.1 | End-to-end integration test with a sample repo | Passing E2E test | `test_e2e_workflow` |
| 7.2 | Write `README.md` with installation & usage instructions | Documentation | — |
| 7.3 | Write `docs/user_guide.md` | Extended documentation | — |
| 7.4 | Record a demo (optional) | Demo video / GIF | — |

### Phase 8 — Stretch Goals (Optional)

| Step | Task | Priority |
|------|------|----------|
| 8.1 | Streamlit web UI (`web/app.py`) | Medium |
| 8.2 | Multi-language support via `tree-sitter` | Medium |
| 8.3 | Dependency graph visualization (Mermaid / Graphviz) | Low |
| 8.4 | Git history analysis (who changed what, how often) | Low |
| 8.5 | Export findings as SARIF (Static Analysis Results Interchange Format) | Low |
| 8.6 | Plugin system for custom analyzers | Low |
| 8.7 | Support for JavaScript/TypeScript projects | Medium |
| 8.8 | Docker-based sandboxing for untrusted repos | High (production) |

---

## 10. Appendix — Glossary & References

### Glossary

| Term | Definition |
|------|-----------|
| **AST** | Abstract Syntax Tree — a tree representation of source code structure |
| **RAG** | Retrieval-Augmented Generation — retrieve relevant context, then generate answers using an LLM |
| **Code Smell** | A surface-level indicator that usually corresponds to a deeper problem in the code |
| **Unified Diff** | A standard format showing the differences between two files, with `+` and `-` lines |
| **Sandbox** | An isolated copy of the repository where changes can be safely made without affecting the original |
| **ChromaDB** | An open-source embedding database optimized for AI applications |
| **Embedding** | A dense vector representation of text that captures semantic meaning |
| **CVE** | Common Vulnerabilities and Exposures — a standardized identifier for security vulnerabilities |

### References

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [GitPython Documentation](https://gitpython.readthedocs.io/)
- [pip-audit Documentation](https://github.com/pypa/pip-audit)

---

> **Next Step:** Review this plan and confirm approval. Once approved, implementation begins with **Phase 0 — Project Bootstrap**.
