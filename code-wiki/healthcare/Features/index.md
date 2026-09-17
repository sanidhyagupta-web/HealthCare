# Features — HealthCare

Last updated: 2026-09-17

**Generated from `Features/*/Index.md` frontmatter — never hand-edit.** If this disagrees with
a feature file's own `depends_on`/`consumed_by`, the feature file wins; regenerate this instead.

## Feature Catalog

### backend-service

| feat_id | Feature | Domain | Criticality | Path |
|---|---|---|---|---|
| [Feat-0001](Feat-0001-async-processing-workers/Index.md) | async-processing-workers | document-processing | high | `workers/`, `queues/` |
| [Feat-0002](Feat-0002-document-ingestion-pipeline/Index.md) | document-ingestion-pipeline | document-ingestion | high | `app/`, `ingestion/`, `storage/` |
| [Feat-0003](Feat-0003-llm-extraction-inference/Index.md) | llm-extraction-inference | llm-inference | medium | `llm/`, `mlx_adapter/`, `scripts/convert_to_mlx.py` |
| [Feat-0004](Feat-0004-security-access-control/Index.md) | security-access-control | security | high | `security/` |
| [Feat-0005](Feat-0005-semantic-search-indexing/Index.md) | semantic-search-indexing | search | high | `search/`, `indexing/` |

### frontend-feature

| feat_id | Feature | Domain | Criticality | Path |
|---|---|---|---|---|
| [Feat-0006](Feat-0006-healthcare-search-upload-ui/Index.md) | healthcare-search-upload-ui | user-interface | high | `ui/` |

### shared-library

| feat_id | Feature | Domain | Criticality | Path |
|---|---|---|---|---|
| [Feat-0007](Feat-0007-platform-data-layer/Index.md) | platform-data-layer | platform | high | `db/`, `monitoring/` |

## Workflow Routing Rules

| Keyword | Load |
|---|---|
| ingest, upload, validate, duplicate, department | Feat-0002 |
| worker, queue, retry, DLQ, parse, OCR, chunk, pipeline stage | Feat-0001 |
| search, retrieval, embedding, rerank, vector, BM25, RAG | Feat-0005 |
| role, RBAC, auth, login, mask, redact, audit, encrypt, guardrail | Feat-0004 |
| extract, ADE, drug, Claude, LLM, MLX | Feat-0003 |
| UI, Streamlit, page, session state | Feat-0006 |
| schema, model, table, migration, database | Feat-0007 |

| Workflow | Section-loading guidance |
|---|---|
| Add a new ingest source | Feat-0002 (Business Rules, API Endpoints), Feat-0001 (Status/State Machine) |
| Change RBAC/masking behavior | Feat-0004 (Access Control), Feat-0005 (Access Control — the architectural finding), Feat-0002 (department/role policy) |
| Add a new worker stage | Feat-0001 (Key Files, Safe vs Dangerous Changes) |
| Change the UI's search flow | Feat-0006 (Key User Flows), Feat-0005 (Access Control) |
| Fix the `/ingest/bulk` auth gap | Feat-0002, Feat-0004 (both Access Control sections) |

## Dependency Graph

See `Architecture/Overview.md`'s Coupling Graph for the full table and the tightest coupling
in the system (Feat-0001 ↔ Feat-0002). Downstream impact summary:

- **Feat-0007** (Platform Data Layer) has no dependencies and the widest blast radius if its
  schema changes — Feat-0001, Feat-0002, Feat-0004, and Feat-0006 all read/write through it.
- **Feat-0004** (Security & Access Control) is depended on by every caller-facing feature
  (Feat-0001, Feat-0002, Feat-0005, Feat-0006) — a change to its RBAC/masking contract has the
  widest downstream reach of any single feature.
- **Feat-0003** (LLM Extraction / Inference) has no dependencies of its own and is the easiest
  feature to change in isolation.
- **Feat-0006** (Healthcare UI) depends on every other feature and is depended on by none —
  it is the system's single top-level consumer, never a dependency itself.
