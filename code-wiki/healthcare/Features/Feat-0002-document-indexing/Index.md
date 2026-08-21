---
feat_id: Feat-0002
feature: document-indexing
type: backend-service
domain: retrieval
criticality: high
touched_paths:
  - indexing/chroma_store.py
  - indexing/embeddings.py
  - indexing/index_schema.py
  - indexing/opensearch_index.py
  - indexing/pii_entity_index.py
  - indexing/reranker.py
depends_on: []
consumed_by: [Feat-0004-pipeline-workers, Feat-0005-semantic-search-qa]
implements: []
tags: [retrieval, vector-search, keyword-search, embeddings]
---

## Overview

| | |
|---|---|
| Type | backend-service |
| Package | `indexing/` |
| Path | `indexing/` |
| Domain | Write-path for the retrieval system: embeddings, vector store, keyword index, reranking |
| Last updated | initial scan |

## Domain Purpose

Turns redacted document chunks into a searchable index — vector embeddings for semantic search,
a keyword (BM25) index for exact-term recall, a hashed PII-entity index for entity-scoped
filtering, and a cross-encoder reranker used at query time to reorder candidates by relevance.

## Entities Owned

No SQL tables — three process-local index stores, none of them SQL-backed:
- Chroma collection `healthcare_docs` (persisted to `data/chroma/`) — see
  [[Schemas/schemas.md#implicit-schema--vectorkeyword-index-chunk-metadata]] for the metadata contract every chunk must carry
- In-memory BM25 corpus, persisted to `bm25_index.json`
- PII entity hash index (`pii_entity_index.json`, `pii_doc_index.json`) — maps `SHA256(entity_type:entity_text)` → chunk IDs

## Invariants

- Every chunk indexed here must already be redacted (PII-masked) — this service does not
  re-check that; it trusts [[Feat-0004-pipeline-workers]]'s `PiiWorker` to have done it first.
- Entity indexing is hash-based; plaintext PII is never persisted into any of the three index stores.
- `PERSON`/`PATIENT_NAME` entity matches expand to *every* chunk in the same document; all other
  entity types return only the specific chunks where they literally appear
  (`indexing/pii_entity_index.py`).
- All three index stores are process-scoped module-level state — restart or scale-out loses the
  BM25 corpus and the PII entity index unless reloaded from their JSON files, and Chroma is the
  only one of the three backed by on-disk persistence designed for that.

## Access Control

**Model**: none in this service — access control (RBAC on `allowed_roles`) is enforced downstream
by [[Feat-0007-security-access-control]], not here. This service returns whatever the query asks for.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Every chunk written here must carry the full `REQUIRED_METADATA_FIELDS` set (patient_id, doc_id, chunk_id, source_file, source_page, source_section, chunk_index, department, allowed_roles) | `indexing/index_schema.py` — **defines** the rule but `validate_metadata()` is never called, so nothing actually enforces it | HIGH (unenforced) |
| BR-02 | Chroma metadata values must be `str`/`int`/`float`/`bool` — lists (like `allowed_roles`) are flattened to a comma-separated string on write | `indexing/chroma_store.py::_sanitise_metadata()` | MEDIUM |
| BR-03 | `PATIENT_NAME`/`PERSON` entity index lookups expand to the whole document's chunks; all other entity types are chunk-scoped | `indexing/pii_entity_index.py` | MEDIUM |
| BR-04 | BM25 upsert replaces an existing entry by `chunk_id` rather than duplicating it | `indexing/opensearch_index.py` | LOW |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| `sentence-transformers` (embedding model, `all-MiniLM-L6-v2` by default) | every chunk embed | CPU/GPU inference, batched (`embedding_batch_size` config) |
| ChromaDB (`PersistentClient`) | every upsert/query | local persistent vector store, no external service |
| Cross-encoder `ms-marco-MiniLM-L-6-v2` | every search rerank | `max_length` hardcoded to 512 — not configurable despite other model params being config-driven |

## Safe vs Dangerous Changes

### Safe
- Swapping the embedding model name in config (re-embedding of existing content is a separate, manual operation — not automatic)
- Adding new optional metadata fields not in `REQUIRED_METADATA_FIELDS`

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing embedding dimensionality (model swap to a different vector size) | Silent query-time failure | Chroma has no explicit dimension check at upsert; a mismatch surfaces as a runtime error only when queried, not at write time |
| Changing `REQUIRED_METADATA_FIELDS` or the `allowed_roles` convention | Breaks [[Feat-0007-security-access-control]]'s RBAC filtering, which reads this metadata by field name | 
| Calling `validate_metadata()` for the first time in production | Could suddenly start rejecting chunks that were previously silently written with missing fields — audit existing data first |

### Human Escalation Required
- Any change to how `allowed_roles` is serialized into Chroma metadata (currently list→comma-string) — this is the sole channel RBAC filtering depends on.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| `chromadb`/`rank-bm25`/`sentence-transformers` not installed | `ImportError` at module load | optional dependency missing |
| Unknown `department` value | `ValueError` (raised in [[Feat-0003-document-ingestion]]'s `rbac_policy.get_allowed_roles()`, not here, but blocks indexing upstream) | department not in the fixed department→role map |
| Vector or keyword search unavailable | caller (Streamlit UI) shows a warning, treated as graceful degradation, not a hard failure | dependency/connectivity issue |
| BM25 index not available | `keyword_search()` returns `[]` | index not built/loaded |

## Testing Expectations

*Open question: no dedicated tests found for `indexing/` in `tests/unit/` — coverage for this
module comes indirectly via [[Feat-0005-semantic-search-qa]]'s `test_researcher_role.py`, which
exercises `secure_results()` end-to-end but not the indexing write path itself.*

## Key Files

- `indexing/chroma_store.py` — vector store wrapper (Chroma `PersistentClient`), metadata sanitization
- `indexing/embeddings.py` — `SentenceTransformer` wrapper
- `indexing/opensearch_index.py` — in-memory BM25 keyword index with JSON persistence (despite the name, this is not actually OpenSearch)
- `indexing/pii_entity_index.py` — hashed PII entity → chunk-id index, `threading.Lock`-protected
- `indexing/reranker.py` — cross-encoder reranking
- `indexing/index_schema.py` — shared metadata field contract (partially unenforced — see BR-01)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0002-document-indexing | touching embeddings, the vector/keyword index, reranking, or the chunk metadata contract |

## Forbidden Patterns

- Never write a chunk to Chroma/BM25 without the full `REQUIRED_METADATA_FIELDS` set, even though nothing currently enforces this — a missing `allowed_roles` silently defaults to "admin only" downstream in [[Feat-0007-security-access-control]], which is a data-visibility bug, not a crash.
- Never assume `pii_entity_index`, the BM25 corpus, or the Chroma client are populated on a fresh process without the corresponding JSON files/persisted collection being present — all three are process-scoped globals.

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| Custom in-memory BM25 instead of a real OpenSearch cluster (despite the module name `opensearch_index.py`) | Keeps the stack to a single local process for this prototype | Renaming the module or introducing a real search cluster — either changes ops assumptions |
| Three separate index stores (vector, keyword, PII-entity) rather than one unified store | Different query patterns (semantic, exact-term, entity-scoped) need different data structures | Adding a new query pattern that could reuse an existing store instead of adding a fourth |
