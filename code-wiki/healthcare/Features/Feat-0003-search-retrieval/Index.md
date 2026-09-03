---
feat_id: Feat-0003
feature: search-retrieval
type: backend-service
domain: healthcare-document-search
criticality: high
touched_paths:
  - search/
  - indexing/
depends_on: [Feat-0005, Feat-0001]
consumed_by: [Feat-0004]
implements: []
tags: [search, rbac, pii-masking, hybrid-retrieval]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | (single package) | `search/`, `indexing/` | Hybrid (vector + keyword) retrieval over redacted medical chunks | 2026-09-03 |

## Domain Purpose

Retrieves relevant, already-redacted document chunks for a user's query via vector search
(Chroma), keyword search (BM25), and cross-encoder reranking, then is *supposed to* apply
query-time role-based access filtering and secondary role-based token masking before an answer is
generated. `search/pipeline.py:secure_results()` defines that mandatory two-step flow — see the
CRITICAL gap below: it is not the code path actually used in production.

## Entities Owned

None directly (this feature reads `chunk_registry`/`document_registry`, owned by
[Feat-0001](../Feat-0001-document-ingestion-pipeline/Index.md)). It writes and owns the
non-relational index structures: [chroma_collection](../../Schemas/schemas.md#chroma_collection-healthcare_docs)
and [bm25_index](../../Schemas/schemas.md#bm25_index-databm25_indexjson).

## Invariants

- **Documented, non-negotiable call order**: `filter_results_by_role` → `apply_role_mask` →
  `generate_answer` (per `AiHarness/skills/access-control.md` and `search/pipeline.py`'s own
  docstring). See Business Rules — this order is violated in the actual UI code path today.
- `apply_role_mask()` never mutates the original chunk dict (returns a shallow copy).
- A `PERSON`/`PATIENT_NAME` match in the user's query expands the pre-filter to every chunk in the
  matched document, not just the matching chunk (`indexing/pii_entity_index.py`).

## Access Control

**Model**: RBAC — same `role` string as the rest of the system, checked against each chunk's
`allowed_roles` metadata (set at ingest time by Feat-0001).

| Action | Access Condition | Enforced In |
|---|---|---|
| Retrieve any chunk (vector or keyword) | `role ∈ chunk.metadata.allowed_roles` or `role == "admin"` | `security/access_control.py:filter_results_by_role()`, called from `ui/search_page.py:_vector_search`/`_keyword_search` |
| Per-role token masking of clinical/PII placeholders | role-specific masked-entity set | `ingestion/pii/role_based_masking.py:apply_role_mask()` — **defined but not called from the live search path** |

## Business Rules

| BR | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | `filter_results_by_role()` is the sole RBAC gate on retrieval; admin bypasses the role check but is still subject to masking downstream *in the designed flow* | `security/access_control.py` | CRITICAL |
| BR-02 | Researcher role must never see `PATIENT_NAME`, `MRN`, `DATE`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `SSN`, `PATIENT_DEMOGRAPHICS` tokens | `ingestion/pii/role_based_masking.py` | CRITICAL |
| BR-03 | Billing role must never see clinical tokens (`LAB_VALUE`, `VITAL_SIGN`, `MEDICATION`, `DOSAGE_FREQ`, `DRUG_DOSE`) | `ingestion/pii/role_based_masking.py` | CRITICAL |
| BR-04 | Admin sees no clinical tokens either — admin's DB-level bypass is metadata-only, not content-masking | `ingestion/pii/role_based_masking.py` | HIGH |
| BR-05 | Unknown/unlisted role → mask **all** detected entity types (fail-safe default) | `ingestion/pii/role_based_masking.py` | HIGH |
| **BR-06** | **`apply_role_mask()` is never called from `ui/search_page.py` — it calls only `filter_results_by_role()` and then proceeds straight to reranking/answer generation** | `ui/search_page.py:45,63` vs. `search/pipeline.py:secure_results()` | **CRITICAL — live access-control gap, not a hypothetical** |
| BR-07 | Query containing a detected PII entity pre-filters candidates to matching chunks/documents only | `indexing/pii_entity_index.py` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| Chroma (vector store) | every query | `indexing/chroma_store.py:query()` |
| BM25 index (JSON-backed) | every query (keyword/hybrid mode) | `indexing/opensearch_index.py:keyword_search()`/`keyword_search_filtered()` |
| Cross-encoder reranker | after retrieval | `indexing/reranker.py:rerank()` |
| Claude API (via `llm/claude_client.py`) | after reranking | `generate_answer()` — this is a *different* LLM integration than [Feat-0002](../Feat-0002-llm-ade-extraction-service/Index.md)'s ADE model |

## API Endpoints

None — this feature is called via direct Python function invocation from
[Feat-0004](../Feat-0004-healthcare-semantic-search-ui/Index.md), not HTTP.
`search/pipeline.py:secure_results()` is the one function meant to be the public entrypoint, but
nothing in production calls it (see GAPS).

## Safe vs Dangerous Changes

### Safe
- Tuning reranker `top_k` or the BM25/vector score-merge weighting.
- Adding a new masked-entity type to `role_based_masking.py`'s per-role sets.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing chunk metadata shape (`allowed_roles`, `entity_types`) | Silently breaks RBAC filtering or masking for existing indexed chunks | No migration/backfill path for already-indexed data |
| Adding a new caller of vector/keyword search that doesn't route through `filter_results_by_role()` | Repeats today's masking gap in a new place | There is no shared "secure retrieval" helper actually enforced — each caller must remember both steps itself |

### Human Escalation Required
- **Wiring `ui/search_page.py` to call `secure_results()` (or `apply_role_mask()` directly) instead of stopping after `filter_results_by_role()`** — this is a live PHI-exposure gap across every non-clinical role (researcher, billing, admin), not a style issue.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Chroma/embedding call fails | `st.warning`, empty result list | `ui/search_page.py:_vector_search` catches broadly |
| BM25 search fails | `st.warning`, empty result list | `ui/search_page.py:_keyword_search` catches broadly |
| `sentence-transformers`/Chroma not installed | `RuntimeError` with install hint | `indexing/embeddings.py`, `indexing/chroma_store.py` |
| Claude API call fails | logged error, error message returned in place of an answer, empty citations | `llm/claude_client.py:generate_answer()` |

## Testing Expectations

- `tests/unit/test_researcher_role.py` covers `apply_role_mask()` and `filter_results_by_role()`
  directly, and `search.pipeline:secure_results()` end-to-end — but **does not exercise the actual
  `ui/search_page.py` code path**, so it cannot catch the BR-06 gap; it tests the correct-but-unused
  function instead of the one actually running in production.

## Forbidden Patterns

- Never call `filter_results_by_role()` without also calling `apply_role_mask()` afterward — the
  documented flow treats these as one inseparable step, and BR-06 is the concrete cost of treating
  them as separable.

## Key Files

- `search/pipeline.py` — `secure_results()`, the intended (but unused) secure retrieval entrypoint
- `indexing/chroma_store.py`, `embeddings.py` — vector search
- `indexing/opensearch_index.py` — BM25 keyword search (despite the module name, this is a
  JSON-persisted in-process BM25 index, not OpenSearch)
- `indexing/reranker.py` — cross-encoder reranking
- `indexing/pii_entity_index.py` — query-time PII entity pre-filter
- `indexing/index_schema.py` — required chunk-metadata fields

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0003 | touching retrieval, ranking, or the RBAC-filter/masking call order |
| Feat-0005 | touching what `filter_results_by_role()`/`apply_role_mask()` themselves do |
| Feat-0004 | touching how the search page calls into this feature |

*Open question: was `ui/search_page.py` written before `apply_role_mask()`/`secure_results()`
existed and never updated, or was the omission intentional for some reason not visible in the
code? Either way this reads as a defect, not a design choice, given `access-control.md`'s explicit
non-negotiable call order.*
