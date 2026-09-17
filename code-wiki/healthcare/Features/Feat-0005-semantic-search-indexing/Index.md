---
feat_id: Feat-0005
feature: semantic-search-indexing
type: backend-service
domain: search
criticality: high
touched_paths:
  - search/
  - indexing/
depends_on: [Feat-0002, Feat-0004]
consumed_by: [Feat-0001, Feat-0006]
implements: []
tags: [search, rag, vector-store, rbac]
---

## Overview

| Field | Value |
|---|---|
| Type | backend-service |
| Package | `search/`, `indexing/` |
| Path | `search/pipeline.py`, `indexing/*.py` |
| Domain | search |
| Last updated | 2026-09-17 |

## Domain Purpose

Stores and retrieves searchable chunk embeddings (dense/Chroma and keyword/BM25), re-ranks
candidates with a cross-encoder, and provides the query-time RBAC filter + PII masking
sequence that turns a raw retrieval result into something a given caller is actually allowed
to see.

## Entities Owned

| Entity | Represents |
|---|---|
| [chunk_metadata](../../Schemas/schemas.md#chunk_metadata-search-index-document-schema--not-a-sql-table) | Per-chunk metadata stored alongside every Chroma/BM25 entry |
| [pii_entity_index](../../Schemas/schemas.md#pii_entity_index-on-disk-json--not-a-sql-table) | SHA256 entity-hash → chunk-ids index, used for query-time PII pre-filtering |
| [pii_document_chunk_index](../../Schemas/schemas.md#pii_document_chunk_index-on-disk-json--not-a-sql-table) | doc↔chunk bidirectional map, used to expand a patient-name hit to the full document |

## Invariants

- Plaintext PII values are never stored in the entity hash index — only SHA256 hashes.
- `entity_types` metadata is produced at chunking time (Feat-0002) but — per this scan's own
  finding — is **not actually persisted** into the Chroma/BM25 metadata dict; see the open
  question below.
- Module-level model/index caches (`embeddings.py`, `reranker.py`, `chroma_store.py`,
  `opensearch_index.py`) are process-scoped — lost on restart, and not safe to assume warm
  across a multi-replica deployment.

## Access Control

**Model**: same RBAC model as the rest of the system (Feat-0004 owns the mechanism, Feat-0002
owns the department→role policy). This feature is where it's applied at *query* time.

| Action | Access Condition | Enforced In |
|---|---|---|
| Return a chunk from search | caller's role ∈ chunk's `allowed_roles`, or caller is `admin` | `security/access_control.py:filter_results_by_role()` (Feat-0004) |
| Show specific PII tokens in a returned chunk | caller's role not in that entity type's forbidden set | `ingestion/pii/role_based_masking.py:apply_role_mask()` (Feat-0002) |

**Architectural finding**: `search/pipeline.py:secure_results()` exists specifically to
enforce the non-negotiable `filter_results_by_role → apply_role_mask` call order in one place.
But the actual caller, `ui/search_page.py` (Feat-0006), does **not** call `secure_results()` —
it calls `filter_results_by_role()` and `apply_role_mask()` directly itself, reimplementing the
same two-step sequence. The dependency-mapper pass found no `ui → search` import edge at all.
*Open question: is `search/pipeline.py` dead code that should either be deleted or actually
wired in as the single enforcement point? Today, correctness depends on `ui/search_page.py`
independently getting the call order right, with no shared code guaranteeing it.*

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | RBAC filter runs before PII masking, never the reverse | `search/pipeline.py:secure_results()` (intended), `ui/search_page.py` (actual call site) | CRITICAL |
| BR-02 | A PII-bearing query pre-filters retrieval to the specific chunks/documents that contain the matched entity (Top-D filtering); `PATIENT_NAME`/`PERSON` hits expand to the whole document, other entity types stay chunk-specific | `indexing/pii_entity_index.py`, called from `ui/search_page.py` | HIGH |
| BR-03 | Hybrid retrieval merges vector + BM25 results via reciprocal rank fusion, weighted by an `alpha` parameter | `ui/search_page.py:_rrf_merge()` | MEDIUM |
| BR-04 | All candidates are re-scored by a cross-encoder before being handed to the LLM | `indexing/reranker.py:rerank()` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| ChromaDB | every search / every `EmbeddingWorker` upsert (Feat-0001) | Dense vector storage and query |
| BM25 (in-process, file-backed) | every search / every `KeywordIndexWorker` upsert (Feat-0001) | Keyword/lexical search |
| sentence-transformers | query and chunk embedding | Raises `RuntimeError` if not installed |

## Safe vs Dangerous Changes

### Safe
- Tuning the RRF `alpha` weighting or the cross-encoder's candidate count.
- Adding a new metadata field to `indexing/index_schema.py`'s `REQUIRED_METADATA_FIELDS`, as long as writers are updated too.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing chunk metadata shape without updating both `EmbeddingWorker`/`KeywordIndexWorker` (writers, Feat-0001) and `filter_results_by_role`/`apply_role_mask` (readers, Feat-0004) | Silent RBAC/masking failure — missing `allowed_roles` degrades to no access, not a visible error | No schema validation at read time, only `validate_metadata()` at write time (not confirmed to be called everywhere) |
| Calling `chroma_store`/`opensearch_index` retrieval functions directly instead of through `secure_results()`/the RBAC+mask sequence | Bypasses access control entirely | Nothing currently prevents this — see the architectural finding above |

### Human Escalation Required
- Deciding whether `search/pipeline.py` should be wired in as the actual enforcement point, given it currently is not.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Embedding model not installed | `RuntimeError("sentence-transformers not installed...")` | `indexing/embeddings.py` |
| ChromaDB not installed/unavailable | `RuntimeError("chromadb not installed...")` | `indexing/chroma_store.py` |
| BM25 unavailable | `keyword_search()` returns `[]`, logged as a warning | `indexing/opensearch_index.py` |
| No results after RBAC filtering | UI shows "No results found" — same as a genuine empty result | `security/access_control.py` returning `[]` is indistinguishable from an empty index to the caller |

## Testing Expectations

- `tests/unit/test_researcher_role.py` covers `filter_results_by_role` + `apply_role_mask` end to end via `secure_results()` — meaning the *test* exercises the code path the real UI doesn't use. Worth reconciling as part of resolving the architectural finding above.

## Forbidden Patterns

- Never call a raw `indexing/*` retrieval function and return its result to a caller without the RBAC filter + PII mask sequence in between, regardless of whether that goes through `search/pipeline.py` or is reimplemented at the call site.

## Key Files

- `search/pipeline.py` — intended RBAC+masking orchestrator (`secure_results`) — see architectural finding
- `indexing/chroma_store.py` — vector search, module-level singleton client/collection cache
- `indexing/opensearch_index.py` — BM25 keyword search, in-memory + JSON-persisted corpus
- `indexing/embeddings.py` — embedding generation, module-level singleton model cache
- `indexing/reranker.py` — cross-encoder re-ranking
- `indexing/pii_entity_index.py` — PII entity hash index, thread-safe JSON persistence
- `indexing/index_schema.py` — `REQUIRED_METADATA_FIELDS` validation

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0004 (Security & Access Control) | changing the RBAC filter or masking rules this feature calls |
| Feat-0006 (Healthcare UI) | changing the actual query-time call sequence (currently lives in `ui/search_page.py`, not here) |

| Workflow | Sections to load |
|---|---|
| Fix the `search/pipeline.py` vs `ui/search_page.py` duplication | Access Control (this architectural finding), Key Files |
| Add a new chunk metadata field | Entities Owned, Safe vs Dangerous Changes |
