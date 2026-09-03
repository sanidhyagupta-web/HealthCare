# Features — HealthCare

Generated from each `Features/Feat-NNNN-*/Index.md`'s frontmatter. Never hand-edit — regenerate
from the source files if this drifts.

## Feature Catalog

### backend-service

| Feat | Feature | Domain | Criticality | Path |
|---|---|---|---|---|
| [Feat-0001](Feat-0001-document-ingestion-pipeline/Index.md) | document-ingestion-pipeline | healthcare-document-ingestion | high | `app/`, `ingestion/`, `workers/`, `queues/`, `storage/`, `monitoring/`, `db/` |
| [Feat-0002](Feat-0002-llm-ade-extraction-service/Index.md) | llm-ade-extraction-service | llm-inference | medium | `llm/`, `mlx_adapter/`, `evaluation/` |
| [Feat-0003](Feat-0003-search-retrieval/Index.md) | search-retrieval | healthcare-document-search | high | `search/`, `indexing/` |

### frontend-feature

| Feat | Feature | Domain | Criticality | Path |
|---|---|---|---|---|
| [Feat-0004](Feat-0004-healthcare-semantic-search-ui/Index.md) | healthcare-semantic-search-ui | healthcare-document-search | high | `ui/` |

### shared-library

| Feat | Feature | Domain | Criticality | Path |
|---|---|---|---|---|
| [Feat-0005](Feat-0005-security-access-control/Index.md) | security-access-control | security | high | `security/` |

## Workflow Routing Rules

| Keyword / Area | Load |
|---|---|
| upload, ingest, chunking, PII redaction (ingest-time), workers, queues, DLQ, state machine | [Feat-0001](Feat-0001-document-ingestion-pipeline/Index.md) |
| ADE extraction, `/extract`, drug/adverse-event, Qwen/MLX model | [Feat-0002](Feat-0002-llm-ade-extraction-service/Index.md) |
| search, vector/keyword retrieval, reranking, RBAC filter, role masking | [Feat-0003](Feat-0003-search-retrieval/Index.md) |
| any Streamlit page, session state, login UI, upload/search/audit UI | [Feat-0004](Feat-0004-healthcare-semantic-search-ui/Index.md) |
| auth, encryption, audit logging, LLM guardrails, RBAC policy definitions | [Feat-0005](Feat-0005-security-access-control/Index.md) |

### Per-Workflow Section Loading

| Workflow | Sections to load |
|---|---|
| Bug fix in a pipeline stage | that feature's Business Rules, Known Error Scenarios, Key Files |
| Adding a new role or department | Feat-0005 Access Control + Business Rules, Feat-0001's `rbac_policy.py` reference, Feat-0003 Business Rules (masking sets) |
| Touching `/ingest/bulk` auth | Feat-0001 API Endpoints + Feat-0005 BR-06 — read both, they describe the same gap from two sides |
| Touching search result assembly | Feat-0003 Invariants + BR-06, Feat-0004 APIs Consumed note — the masking gap is documented in both |

## Dependency Graph

Mandatory dependencies (a change to the dependency can break the dependent):

| Feature | Depends On | Why |
|---|---|---|
| Feat-0001 | Feat-0005 | audit logging, encryption |
| Feat-0001 | Feat-0002 | ADE extraction call (HTTP, only cross-process edge) |
| Feat-0003 | Feat-0005 | RBAC filter, role masking |
| Feat-0003 | Feat-0001 | reads `chunk_registry`/`document_registry`, consumes `rbac_policy.py` |
| Feat-0004 | Feat-0001, Feat-0003, Feat-0005 | every backend call the UI makes |

Downstream impact (if this feature breaks, what else breaks):

| Feature | Breaks |
|---|---|
| Feat-0005 | Feat-0001, Feat-0003, Feat-0004 (auth, RBAC, encryption, audit — used everywhere) |
| Feat-0001 | Feat-0003 (reads its tables), Feat-0004 (uploads) |
| Feat-0002 | Feat-0001's extraction stage only (degrades gracefully — pipeline continues without ADE data) |
| Feat-0003 | Feat-0004's search page only |

See [Architecture/Overview.md](../Architecture/Overview.md) for the rendered coupling graph and
cross-cutting decisions.
