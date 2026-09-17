# Features Index

**Generated from frontmatter — never hand-edit.** If this disagrees with a feature's own frontmatter,
the frontmatter wins; regenerate this file instead.

## Feature Catalog

### backend-service

| feat_id | feature | domain | criticality | path |
|---|---|---|---|---|
| Feat-0001 | app | api-bootstrap | high | `app/` |
| Feat-0002 | indexing | retrieval-index | high | `indexing/` |
| Feat-0003 | ingestion | document-intake | high | `ingestion/` |
| Feat-0004 | llm | model-inference | medium | `llm/` |
| Feat-0005 | search | rag-query-pipeline | high | `search/` |
| Feat-0006 | security | auth-rbac-audit | high | `security/` |
| Feat-0007 | workers | async-pipeline-execution | high | `workers/`, `queues/` |

### frontend-feature

| feat_id | feature | domain | criticality | path |
|---|---|---|---|---|
| Feat-0008 | ui | streamlit-app | high | `ui/` |

### shared-library

| feat_id | feature | domain | criticality | path |
|---|---|---|---|---|
| Feat-0009 | platform | infra | high | `storage/`, `db/`, `monitoring/` |

## Workflow Routing Rules

### Keyword → Feature File

| Keyword / concept | Feature |
|---|---|
| upload, bulk ingest, `/ingest/bulk`, rate limiter | Feat-0001-app |
| Chroma, BM25, embeddings, rerank, PII entity index | Feat-0002-indexing |
| validation, state machine, `DocStatus`, PII redaction, RBAC policy, department, chunking | Feat-0003-ingestion |
| ADE extraction, MLX, Claude API, drug/adverse-effect | Feat-0004-llm |
| `secure_results`, filter-then-mask ordering | Feat-0005-search |
| login, session, `filter_results_by_role`, audit log, encryption, guardrails | Feat-0006-security |
| worker, queue, DLQ, retry, parser/markdown/chunking/pii/extraction/embedding/keyword-index worker | Feat-0007-workers |
| Streamlit, any `ui/*.py` page | Feat-0008-ui |
| S3, KMS, SQLAlchemy, `db/models.py`, tracing | Feat-0009-platform |

### Per-Workflow Section-Loading Table

| Workflow | Load |
|---|---|
| Adding a new API endpoint | Feat-0001-app (API Endpoints, Access Control) |
| Adding/changing a role or department | Feat-0003-ingestion (Access Control, BR-01/BR-06), Feat-0006-security (Access Control) |
| Debugging a stuck document | Feat-0003-ingestion (Status/State Machine), Feat-0007-workers (Known Error Scenarios) |
| Investigating a PII-in-LLM-answer report | Feat-0005-search (Human Escalation Required), Feat-0008-ui (BR-03) |
| Changing the vector/keyword index schema | Feat-0002-indexing, then Architecture/Overview.md's High-Risk Couplings |
| Touching `app/config.py:Settings` | Architecture/Overview.md's Settings decision, then every feature's Overview/Dependencies |

## Dependency Graph

See `Architecture/Overview.md`'s Coupling Graph and High-Risk Couplings sections — this index does
not duplicate them; the frontmatter `depends_on`/`consumed_by` fields on each feature page are the
canonical record.

## Open Questions Raised During This Scan

- *Is `evaluation/run_eval.py` a feature in its own right, given it duplicates production query logic and inherits the same PII-masking gap as `ui/search_page.py`?* (Feat-0005-search, Architecture/Overview.md)
- *Should `document_registry.original_filename` carry a `UNIQUE` constraint?* (Schemas/schemas.md)
- *Should `chunk_registry`/`audit_log` get real `ForeignKey` declarations?* (Schemas/schemas.md, Feat-0009-platform)
- *Is `chunk_registry.is_redacted` intentionally `Integer` rather than `Boolean`?* (Schemas/schemas.md)
- *Should `indexing/index_schema.py:validate_metadata()` be wired into `upsert_chunks()`?* (Feat-0002-indexing)
- *Is there any test coverage for the RBAC/state-machine guard functions themselves, independent of a full pipeline run?* (Feat-0003-ingestion, Feat-0006-security)
- *Is there any test exercising an actual worker instance, rather than just the ingest→enqueue boundary?* (Feat-0007-workers)
