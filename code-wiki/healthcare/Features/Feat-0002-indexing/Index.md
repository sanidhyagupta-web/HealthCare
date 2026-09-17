---
feat_id: Feat-0002
feature: indexing
type: backend-service
domain: retrieval-index
criticality: high
touched_paths:
  - indexing/opensearch_index.py
  - indexing/reranker.py
  - indexing/chroma_store.py
  - indexing/pii_entity_index.py
  - indexing/index_schema.py
  - indexing/embeddings.py
depends_on: [platform]
consumed_by: [ui, workers]
implements: []
tags: [rag, vector-store, keyword-search, pii]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | `indexing` | `indexing/` | Vector + keyword + PII-entity indexing | 2026-09-17 (initial scan) |

## Domain Purpose

Builds and serves the three retrieval indexes a query needs: a Chroma vector store, an in-memory
BM25 keyword index, and a hash-only PII entity index used to pre-filter search by detected patient
identifiers. Also owns cross-encoder reranking of retrieved candidates.

## Entities Owned

- [chroma_vector_store](../../Schemas/schemas.md#chroma_vector_store-not-sql--chroma-persistent-collection) — vector embeddings per chunk
- [bm25_keyword_index](../../Schemas/schemas.md#bm25_keyword_index-not-sql--json-persisted) — keyword index, JSON-persisted
- [pii_entity_index](../../Schemas/schemas.md#pii_entity_index-not-sql--hash-based-json-persisted) — SHA-256 PII entity hashes, never plaintext

## Invariants

- No plaintext PII is ever written into `pii_entity_index` — only `sha256(entity_type:entity_value)` hashes (`indexing/pii_entity_index.py:18`).
- Chroma metadata values must be scalar (`str`/`int`/`float`/`bool`); `allowed_roles` (a list) is joined into a comma-delimited string at write time (`indexing/chroma_store.py:76-87`) — see the Schemas note on why this is a risk.
- Chunk IDs are the shared key across all three indexes and must stay unique.
- Module-level embedding and reranker models are singletons, loaded once per process — lost on restart/scale-out.

## Access Control

**Model**: none directly enforced here — `indexing` returns raw candidates; RBAC filtering happens
downstream in [[security]]'s `filter_results_by_role`. `allowed_roles` metadata written per-chunk is
sourced from [[ingestion]]'s RBAC policy, not decided in this module.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | `validate_metadata()` exists to check required chunk-metadata fields but is **never called** before `upsert_chunks()` | `indexing/index_schema.py` (defined, unused) | HIGH |
| BR-02 | `PERSON`/`PATIENT_NAME` PII-entity hits expand results to the whole matched document; all other entity types return only the matching chunks | `indexing/pii_entity_index.py:6-16` | MEDIUM |
| BR-03 | BM25 keyword search returns `[]` (not an error) if `rank-bm25` isn't installed, or if the corpus is empty | `indexing/opensearch_index.py:30-32, 60-63` | LOW |
| BR-04 | Reranker returns only non-zero-score candidates, capped at `top_k` | `indexing/reranker.py:37-48` | LOW |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| ChromaDB (local persistent) | every upsert/query | vector embeddings stored/read from `data/chroma` |
| sentence-transformers | embedding + reranking | loads `all-MiniLM-L6-v2` (configurable) and a cross-encoder model on first use |

## Safe vs Dangerous Changes

### Safe
- Adjusting the reranker's `top_k`.
- Adding a new metadata field to `index_schema.py`'s required-fields list (as long as writers are updated too).

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing how `allowed_roles` is serialized into Chroma metadata | Silent RBAC bypass or false-deny | Downstream role check must parse whatever format is written; a substring-match bug here is a real, documented failure mode (see `AiHarness/skills/access-control.md`) |
| Wiring `validate_metadata()` into `upsert_chunks()` | Could start rejecting chunks that previously silently succeeded without required fields | Verify no current writer omits a required field first |
| Changing the embedding model without a re-embed of existing data | Query/document embedding-space mismatch — silently wrong retrieval, no error | No embedding-model version is tracked anywhere in the index |

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| `chromadb` not installed | `RuntimeError` | `indexing/chroma_store.py:27-28` |
| embedding library not installed | `RuntimeError` | `indexing/embeddings.py:19-20` |
| BM25 JSON corrupted on disk | `json.JSONDecodeError` at module import — the whole module fails to load | `indexing/opensearch_index.py` `_load()` |
| `rerank()` called with a candidate dict missing a `text` key | unhandled `KeyError` | `indexing/reranker.py` (no validation) |

## Testing Expectations

- No dedicated test file for `indexing/` was found in `tests/unit/`; coverage for RBAC-adjacent
  behavior comes indirectly via `tests/unit/test_researcher_role.py`, which exercises
  `filter_results_by_role` (in [[security]]) against fixture chunk metadata, not the indexing layer
  itself.

## Forbidden Patterns

- Never store `allowed_roles` as anything other than a value that round-trips correctly through
  whatever format the index actually persists it in — a comma-joined string that gets substring-matched
  instead of list-membership-checked is a known failure mode.

## Key Files

- `indexing/chroma_store.py` — vector store upsert/query
- `indexing/opensearch_index.py` — BM25 keyword index, JSON-persisted, no thread lock
- `indexing/pii_entity_index.py` — hash-only PII entity index, thread-locked
- `indexing/reranker.py` — cross-encoder reranking
- `indexing/embeddings.py` — text embedding generation
- `indexing/index_schema.py` — required chunk-metadata fields (`validate_metadata()` unused)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0002-indexing | touching Chroma/BM25/PII-index read or write paths, or reranking |

| Workflow | Sections to load |
|---|---|
| Debugging a search result that seems RBAC-wrong | Entities Owned → [[security]] Access Control → this file's `allowed_roles` note |
| Adding a new index consumer | Dependencies note in Architecture/Overview.md, then Key Files here |
