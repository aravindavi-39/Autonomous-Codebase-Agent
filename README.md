# Autonomous Codebase Understanding & Refactor Agent

An AI-powered agent that can understand an unfamiliar software repository and safely help developers analyze and refactor it.

---

## Features

- **Repository Ingestion** — Ingest local repositories safely with validation, secret filtering, and file discovery.
- **Python AST Analysis** — Structural extraction of imports, classes, functions, calls, exceptions, and line numbers without code execution.
- **Codebase Relationship Graph** — Build a `CodeGraph` tracking `IMPORTS`, `DEFINES`, `CALLS`, `INHERITS`, `CONTAINS`, `TESTS`, and `DEPENDS_ON` relationships, including cycle detection.
- **Grounded Codebase Q&A** — Natural-language question answering powered by hybrid retrieval (semantic vector search + structural graph queries) with verified citations.
- **Code Smell & Maintainability Analysis** — AST and graph-based static detection of complex functions, high parameter counts, deep nesting, god classes, dead functions, circular dependencies, excessive fan-out, and duplicate logic.
- **Static Security Auditing** — AST-level pattern detection for hardcoded secrets, dangerous dynamic execution (`eval`/`exec`), shell injection, unsafe deserialization (`pickle`), SQL injection risks, weak crypto, disabled TLS, and debug flags.
- **Problematic Coding Patterns** — Detection of broad `except` blocks, mutable default arguments, wildcard imports, shadowing built-in names, unused imports, and unreachable dead code.
- **Refactoring Planning & Safe Diff Generation** — Prioritized refactoring plans from static findings, deterministic transformations for safe patterns, unified diff generation, and temp-copy validation without modifying the original repository.
- **Safe Sandbox Application & Verification** — Isolated temporary repository creation, strict human approval gate (`--approve`), safe patch application, subprocess test suite execution, regression verification, and automatic cleanup.

---

## Requirements

- Python 3.11 or higher
- pip

---

## Quick Start

### 1. Setup Virtual Environment & Dependencies

```bash
# Clone and enter directory
cd Autonomous-Codebase-Agent

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# source venv/bin/activate   # Linux / macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure the API Key

Create a `.env` file in the project root (or copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=sk-your-openai-api-key-here
LLM_MODEL=gpt-4o-mini
```

> **Note:** Never commit `.env` or hard-code API keys. The application only reads credentials from environment variables or `.env`.

---

## CLI Usage

### Index and Ingest a Repository (`load`)

```bash
codebase-agent load tests/fixtures/sample_repo --export-json manifest.json
```

### Code Smell & Security Analysis (`analyze`)

Run static code smell, security, and pattern analysis across the codebase:

```bash
codebase-agent analyze tests/fixtures/sample_repo
```

#### CLI Flags & Filtering

```bash
# Filter by minimum severity
codebase-agent analyze tests/fixtures/sample_repo --severity high

# Filter by finding category
codebase-agent analyze tests/fixtures/sample_repo --category security

# Output report directly as JSON
codebase-agent analyze tests/fixtures/sample_repo --json

# Export combined AST metrics and findings to file
codebase-agent analyze tests/fixtures/sample_repo --export-json findings.json

# Disable specific analysis categories
codebase-agent analyze tests/fixtures/sample_repo --no-security --no-patterns
```

#### Supported Rule Catalog

- **Security Rules (`SECURITY`):**
  - `SEC-001`: Hardcoded secrets, passwords, tokens, API keys (with automatic evidence redaction)
  - `SEC-002`: Dangerous dynamic execution (`eval`, `exec`, dynamic `compile`)
  - `SEC-003`: Unsafe subprocess execution with `shell=True`
  - `SEC-004`: Unsafe deserialization (`pickle.loads`, `pickle.load`)
  - `SEC-005`: SQL injection risks via dynamically formatted queries
  - `SEC-006`: Command injection risks via `os.system` / `os.popen`
  - `SEC-007`: Path traversal risks via unvalidated dynamic paths in `open()`
  - `SEC-008`: Weak cryptographic hashing algorithms (`MD5`, `SHA-1`)
  - `SEC-009`: Disabled TLS/SSL certificate validation (`verify=False`)
  - `SEC-010`: Insecure development/debug settings (`debug=True`)

- **Code Smell Rules (`CODE_SMELL`):**
  - `SMELL-001`: Long functions (exceeding line length threshold)
  - `SMELL-002`: High parameter count (functions with excessive parameters)
  - `SMELL-003`: Deep control flow nesting (excessive indentation/nesting depth)
  - `SMELL-004`: Too many branches (high cyclomatic branch decision points)
  - `SMELL-005`: Large classes (classes with excessive methods or lines)
  - `SMELL-006`: Dead functions (unreferenced functions with no calls detected)
  - `SMELL-007`: Circular dependencies (module import cycles detected in graph)
  - `SMELL-008`: Excessive dependencies (files with high module fan-out)
  - `SMELL-009`: Missing documentation (public classes or functions lacking docstrings)
  - `SMELL-010`: Duplicate logic (repeated AST statement sequence blocks)

- **Coding Pattern Rules (`PATTERN`):**
  - `PAT-001`: Broad exception handlers (`except:` or `except Exception:`)
  - `PAT-002`: Wildcard imports (`from module import *`)
  - `PAT-003`: Mutable default arguments (`def f(items=[]):`)
  - `PAT-004`: Shadowing built-in identifiers (`id`, `type`, `list`, `str`)
  - `PAT-005`: Unused imports (imported modules/symbols never referenced)
  - `PAT-006`: Unreachable code (dead code following `return`, `raise`, `break`)

#### Severity & Confidence

- **Severity:** `CRITICAL` > `HIGH` > `MEDIUM` > `LOW` > `INFO`
- **Confidence:** `HIGH` (definitive syntactic pattern), `MEDIUM` (semantic heuristic), `LOW` (requires runtime intent check)

> [!IMPORTANT]
> **Static Analysis Disclaimer:**
> All findings produced by the analysis engine are based purely on static syntactic and graph-level heuristics. Static analysis identifies patterns that *resemble* vulnerabilities or code smells; it does **not** prove that a vulnerability is exploitable at runtime. Manual review is always required.

### Codebase Relationship Graph (`graph`)

```bash
codebase-agent graph tests/fixtures/sample_repo --export-json graph.json
```

---

## Refactoring Planning & Safe Diff Generation (`plan` & `diff`)

The agent translates verified static analysis findings into actionable, prioritized refactoring plans and generates deterministic unified diffs.

> [!IMPORTANT]
> **Repository Immutability Guarantee:**
> Target repositories are strictly read-only. The agent **never** modifies the original repository during planning, diff generation, or validation. Diff validation is executed strictly against temporary copies in isolated directories.

### 1. Generate a Refactoring Plan (`plan`)

Generate a prioritized plan of recommended refactoring actions:

```bash
codebase-agent plan tests/fixtures/vulnerable_repo
```

#### Plan Filtering Options

```bash
# Only include safe, automated proposals (excludes review-required and unsupported items)
codebase-agent plan tests/fixtures/vulnerable_repo --safe-only

# Filter plan to a specific finding ID
codebase-agent plan tests/fixtures/vulnerable_repo --finding PAT-003_65904b66

# Output plan as JSON
codebase-agent plan tests/fixtures/vulnerable_repo --json

# Export plan to file
codebase-agent plan tests/fixtures/vulnerable_repo --output plan.json
```

### 2. Generate Unified Diffs (`diff`)

Produce unified diffs for proposed changes and validate them on temporary copies:

```bash
# Generate and preview diffs for all safe proposals
codebase-agent diff tests/fixtures/vulnerable_repo --safe-only

# Generate diff for a specific finding
codebase-agent diff tests/fixtures/vulnerable_repo --finding PAT-003_65904b66

# Export generated diffs to a patch file
codebase-agent diff tests/fixtures/vulnerable_repo --safe-only --output refactor.patch
```

### 3. Safety Classifications

Every proposal is assigned one of three strict safety tiers:

| Safety Tier | Meaning | Behavior |
|-------------|---------|----------|
| `SAFE_AUTOMATIC_PROPOSAL` | Deterministic, semantics-preserving transformation. | Diffs automatically generated and validated on temporary copy. |
| `REVIEW_REQUIRED` | Transformation requires developer judgment or context. | Advisory finding; no blind code rewriting without human review. |
| `UNSUPPORTED` | Creative or structural refactoring unsuitable for automation. | Architectural recommendation provided; manual refactoring recommended. |

### 4. Refactoring Strategies Catalog

| ID | Strategy | Target Finding | Safety Tier | Transformation Applied |
|---|---|---|---|---|
| A | `MutableDefaultStrategy` | `PAT-003` | `SAFE_AUTOMATIC_PROPOSAL` | Replaces mutable default (`items=[]`) with `None` + body guard (`if items is None: items = []`). |
| B | `WildcardImportStrategy` | `PAT-002` | `REVIEW_REQUIRED` | Flags for manual review to identify and specify explicit imports. |
| C | `BroadExceptionStrategy` | `PAT-001` | `REVIEW_REQUIRED` | Flags for manual review to catch specific expected exceptions. |
| D | `LongFunctionStrategy` | `SMELL-001` | `UNSUPPORTED` | Architectural recommendation to decompose function into smaller helpers. |
| E | `HighParameterCountStrategy` | `SMELL-002` | `UNSUPPORTED` | Architectural recommendation to introduce parameter object / dataclass. |
| F | `UnusedImportStrategy` | `PAT-005` | `SAFE_AUTOMATIC_PROPOSAL` | Safely removes unused import statement or unused identifier. |
| G | `DebugTrueStrategy` | `SEC-010` | `SAFE_AUTOMATIC_PROPOSAL` | Replaces `debug=True` / `DEBUG = True` with `debug=False` / `DEBUG = False`. |
| H | `WeakCryptoStrategy` | `SEC-008` | `REVIEW_REQUIRED` | Recommends `hashlib.sha256` without auto-rewriting to avoid breaking hash length assumptions. |

---

## Safe Sandbox Application & Verification (`apply`)

The agent provides an isolated verification sandbox to test proposed refactorings without ever modifying the original repository.

> [!IMPORTANT]
> **Strict Safety Invariants:**
> - **Human Approval Boundary:** Patch application requires explicit approval via `--approve`. Without this flag, execution terminates immediately and no sandbox is created.
> - **Original Repository Immutability:** Phase 7 **never** applies changes directly to the original repository. Approved changes are applied and verified exclusively inside an isolated sandbox directory.
> - **Safe-Only Gate:** Only `SAFE_AUTOMATIC_PROPOSAL` actions are eligible for sandbox application. `REVIEW_REQUIRED` and `UNSUPPORTED` proposals are strictly blocked.
> - **Pre-patch Stale Check:** The agent verifies that current source code matches expected lines before applying any edit. Stale proposals are rejected.

### 1. Apply and Verify in Sandbox (`apply`)

```bash
# Requires explicit human approval (--approve)
codebase-agent apply tests/fixtures/vulnerable_repo --finding PAT-003_65904b66 --approve
```

#### CLI Flags & Options

```bash
# Attempting without approval will be rejected:
codebase-agent apply tests/fixtures/vulnerable_repo --finding PAT-003_65904b66
# Output: Explicit approval is required before applying this proposal to a sandbox.

# Skip test execution (useful if the project has no test suite)
codebase-agent apply tests/fixtures/vulnerable_repo --finding PAT-003_65904b66 --approve --no-tests

# Retain sandbox directory for manual developer inspection
codebase-agent apply tests/fixtures/vulnerable_repo --finding PAT-003_65904b66 --approve --keep-sandbox

# Configure test runner timeout (in seconds)
codebase-agent apply tests/fixtures/vulnerable_repo --finding PAT-003_65904b66 --approve --timeout 45

# Output verification report as structured JSON
codebase-agent apply tests/fixtures/vulnerable_repo --finding PAT-003_65904b66 --approve --json
```

### 2. Regression Verdicts

| Status | Meaning |
|---|---|
| `PASS` | All tests passed before and after patch. Zero regressions detected. |
| `FAIL` | New test failures were introduced after patch application. |
| `BASELINE_FAILURE` | Test suite was already failing prior to patch application. |
| `TEST_TIMEOUT` | Test execution exceeded configured timeout limit. |
| `TEST_ERROR` | An execution error occurred while running the test suite. |
| `SYNTAX_ERROR` | Patch introduced a Python syntax error. |
| `NO_TESTS` | No tests were discovered in the repository. |
| `SKIPPED` | Test execution was explicitly skipped via `--no-tests`. |

---

## Verification Engine & Resolution Audit (`verify`)

Phase 8 provides an evidence-based verification engine and refactoring resolution audit to mathematically guarantee that refactorings actually resolve the targeted finding without introducing regressions or secondary code smells.

> [!IMPORTANT]
> **Strict Verification Invariants:**
> - **Evidence-Based Resolution:** `target_resolved=True` is verified by baseline finding presence and post-patch absence using the existing static analysis engine. Passing tests alone never establish resolution.
> - **Accurate Delta Classification:** Accurately distinguishes baseline findings, resolved findings, remaining findings, and genuinely new introduced findings. Pre-existing findings whose line numbers shifted are never misclassified as new.
> - **Deterministic Policies:** `STRICT` mode rejects any newly introduced findings or lint warnings. `LENIENT` mode permits cosmetic warnings but still rejects errors or unresolved targets.
> - **Strictly Read-Only on Target:** `verify` operates on isolated sandboxes and temporary environments, keeping the original repository 100% byte-for-byte immutable.

### 1. Verify Refactoring Resolution (`verify`)

```bash
# Verify a specific finding refactoring with default strict policy
codebase-agent verify tests/fixtures/sandbox_test_repo --finding PAT-003_7fffc35b

# Use lenient policy (permits cosmetic warnings like line-length or whitespace)
codebase-agent verify tests/fixtures/sandbox_test_repo --finding PAT-003_7fffc35b --policy lenient

# Skip tests or linting during verification audit
codebase-agent verify tests/fixtures/sandbox_test_repo --finding PAT-003_7fffc35b --no-tests --no-lint

# Output verification report as structured JSON or export to file
codebase-agent verify tests/fixtures/sandbox_test_repo --finding PAT-003_7fffc35b --json
codebase-agent verify tests/fixtures/sandbox_test_repo --finding PAT-003_7fffc35b --output report.json
```

### 2. Verification Verdicts

| Verdict | Meaning |
|---|---|
| `VERIFIED` | Target finding is confirmed resolved, all tests passed, and no new violations introduced. |
| `REJECTED_REGRESSION` | Patch broke tests or introduced new code smells / lint errors. |
| `REJECTED_UNRESOLVED` | Target finding is still present in the codebase after patch application. |
| `INCONCLUSIVE` | Verification could not definitively determine resolution status. |

---

## Streamlit Web UI (Phase 8.1 Stretch Goal)

In addition to the CLI, the agent includes an interactive browser-based dashboard for visual exploration and safe refactoring:

```bash
# Install optional web dependencies
pip install -r requirements-web.txt
# or: pip install ".[web]"

# Launch the Streamlit dashboard
streamlit run web/app.py
```

### Unified 11-Page Architecture
The web application provides a complete visual interface across 11 dedicated pages:
1. **📊 Dashboard:** Project-wide health overview, high-level metrics, and phase execution pipeline status.
2. **📁 Repository & Ingestion:** File tree, language breakdown, metadata statistics, and interactive file content viewer.
3. **🧠 Code Understanding:** In-depth AST construct exploration (classes, methods, functions, imports, invocations).
4. **🕸️ Architecture & Graph:** CodeGraph relationship traversal, dependency hotspots, and circular dependency detection.
5. **💬 Codebase Q&A:** Grounded natural-language architectural Q&A with validated file:line source citations.
6. **🔍 Findings & Security:** Filterable security vulnerabilities, code smells, and anti-patterns with verbatim evidence code.
7. **🛠️ Refactoring & Diffs:** Actionable refactoring proposals, safety tier filtering, and syntax-highlighted unified diffs.
8. **🧪 Sandbox Apply:** Strict approval-gated sandbox patch execution with baseline/post-patch test regression comparison.
9. **📋 Verification Engine:** Standalone multi-check verification auditing unit tests, AST linter syntax rules, and finding resolution.
10. **📑 Reports & Exports:** Centralized export center for downloading structured JSON reports and diff `.patch` files.
11. **🛡️ Safety & Settings:** Real-time SHA-256 immutability monitoring, safety invariant verification, and LLM configuration.

---

## Asking Questions (`ask`)

Ask natural-language questions about an analyzed codebase:

```bash
codebase-agent ask <repository-path> "<question>"
```

### Example Questions

```bash
# Understand architecture and entry point
codebase-agent ask tests/fixtures/sample_repo "How does the application start and initialize?"

# Query data models
codebase-agent ask tests/fixtures/sample_repo "What data models exist and what fields do they define?"

# Query utilities
codebase-agent ask tests/fixtures/sample_repo "How is file hashing implemented?"
```

### Offline / Mock Mode (`--mock`)

Run Q&A in offline mock mode without an API key or external network requests:

```bash
codebase-agent ask tests/fixtures/sample_repo "What classes exist?" --mock
```

### Advanced Retrieval Options

```bash
# Retrieve top 10 chunks with custom context budget
codebase-agent ask tests/fixtures/sample_repo "Explain the app creation flow" --top-k 10 --max-context 16000

# Disable semantic vector search (use only structural graph queries)
codebase-agent ask tests/fixtures/sample_repo "What does create_app call?" --no-semantic

# Disable graph queries (use only semantic vector search)
codebase-agent ask tests/fixtures/sample_repo "Describe user models" --no-graph
```

---

## Vector Storage & ChromaDB

The agent integrates a local, persistent vector store using **ChromaDB** (`ChromaVectorStore`), as planned in `PROJECT_PLAN.md`:
- **Local & File-backed:** ChromaDB collections store embeddings, code chunks, and metadata locally.
- **Abstract Interface:** Extends `BaseVectorStore` with `LocalVectorStore` fallback for lightweight in-memory environments.
- **Rich Metadata:** Preserves relative file paths, start and end line bounds, programming language, chunk type, and entity symbols.
- **Privacy & Safety:** All chunks and metadata pass through automatic secret detection and redaction prior to embedding and indexing.
- **Zero External Network Calls:** Embeddings are generated locally or through the configured provider; ChromaDB does not contact external endpoints or telemetry.

---

## Citation Format & Verification

Every factual statement made by the agent includes exact source citations:

```
Sources:
📄 src/models.py:8-13 (User)
📄 src/models.py:17-23 (Post)
```

- **Format:** `📄 <file-path>:<start_line>-<end_line> (<entity-name>)`
- **Validation:** Every citation is verified against physical file bounds, AST symbol indices, and actually retrieved context. Hallucinated files, out-of-bound line ranges, and unretrieved files are automatically marked invalid and rejected.

---

## Security & Privacy Behavior

The agent follows strict safety rules:
- **Read-Only / Safe:** Target repository files are never executed, modified, or written to during ingestion, analysis, graph generation, or Q&A. All cache and index data is stored in agent storage or memory, never inside the target repository.
- **Secret Filtering & Redaction:** `.env` files, `.git/`, credentials, and private keys are excluded at discovery. Any sensitive tokens (OpenAI keys, AWS keys, passwords, bearer tokens) are automatically redacted (`[REDACTED_...]`) before embedding, context assembly, or answer presentation.
- **Bounded Context:** Only retrieved chunks relevant to the question are provided to the LLM (bounded by configurable character and chunk limits).
- **Grounded Responses:** The LLM is instructed under strict system rules to answer exclusively from observed code and clearly state when information is missing without fabricating architectures.

---

## Running Tests

```bash
pytest tests/ -v
```

All 464 tests run completely offline without external network calls.

---

## License

MIT
