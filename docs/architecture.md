# System Architecture

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                     │
│                                                             │
│   CLI Interface (Typer / Rich)    Streamlit Web UI (11 Pages)│
│       src/cli/main.py                  web/app.py           │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                         CORE ENGINES                        │
│                                                             │
│  • Ingestion & Validation       (src/ingestion/)            │
│  • AST Analysis & Indexing      (src/analysis/)             │
│  • CodeGraph & Dependencies     (src/analysis/graph_*.py)   │
│  • Code Smells & Security Rules (src/analysis/findings/)    │
│  • Hybrid Vector/Graph QA       (src/retrieval/)            │
│  • Citation Validation          (src/citations/)            │
│  • Refactoring Planner & Diffs  (src/refactoring/)          │
│  • Sandbox & Approval Manager   (src/sandbox/)              │
│  • Verification Engine & Audit  (src/verification/)         │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
    ┌────────────────────┐          ┌────────────────────┐
    │ Target Repository  │          │ Isolated Sandbox   │
    │ (Strictly Read-Only│          │ (Disposable Tempdir│
    │  Verified SHA-256) │          │  Safe Patch Apply) │
    └────────────────────┘          └────────────────────┘
```

For detailed specifications:
- Web UI architecture: see [docs/web_ui.md](web_ui.md)
- Complete roadmap & invariants: see [PROJECT_PLAN.md](../PROJECT_PLAN.md)
