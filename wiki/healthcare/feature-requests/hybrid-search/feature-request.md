---
title: "Hybrid Semantic Search"
slug: hybrid-search
owners:
  - Sanidhya Gupta
status: active
last_updated: 2026-08-22
proposed_by: agent
identity_confirmed: false
---

## Current State
No search endpoint or UI exists yet — the ingestion pipeline (chunk, embed, write to vector store) is stable, but nothing lets a clinician query it. A single search endpoint has been decided: it runs a BM25 keyword query and a vector similarity query in parallel and combines the two ranked lists with reciprocal rank fusion (RRF), so the UI only ever sees one ranked list ([DEC-0002](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md)). The team will stay on an off-the-shelf embedding model rather than fine-tuning a custom clinical one this quarter, and will instead invest in improving chunking ([DEC-0004](../../decisions/DEC-0004_reject-custom-embedding-model-finetuning.md)).

## Key Facts
- Pure vector search was found to lose on exact terms (e.g. a search for "metoprolol" returned documents about "atenolol", a different but related drug) — the motivating case for hybrid retrieval ([DEC-0002](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md)).
- Measured chunking currently splits mid-sentence in about 11% of chunks, identified as a bigger source of bad results than embedding quality ([DEC-0004](../../decisions/DEC-0004_reject-custom-embedding-model-finetuning.md)).

## Requirements
- Single search endpoint accepting a query string, an optional filter on document type and date range, and a result limit defaulting to 20 ([DEC-0002](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md)).
- Returns a ranked list where each result carries the chunk text, source document id, page number, and fusion score ([DEC-0002](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md)).
- Must respond in under 800ms at p95 ([DEC-0002](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md)).
- Must respect the caller's access scope, with the access filter applied inside the query itself — not by filtering after retrieval ([DEC-0002](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md)).
- Chunking investment improves the production `entity_preserving_chunker.py` (not a switch to the unused `semantic_chunker.py`) as the replacement for the fine-tuning work that was ruled out, targeting ≤2% mid-sentence chunk splits (from ~11%) and zero splits inside protected medical entity groups ([DEC-0007](../../decisions/DEC-0007_embedding-finetuning-ticket-scope-resolved.md)).

## Business Rules
- Nothing recorded yet.

## Decisions
| Date | Title | Type | Ticket |
|---|---|---|---|
| 2026-08-21 | [Hybrid retrieval search endpoint (BM25 + vector + RRF)](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md) | decided | _draft, not yet filed_ |
| 2026-08-21 | [Reject custom clinical embedding model fine-tuning this quarter](../../decisions/DEC-0004_reject-custom-embedding-model-finetuning.md) | rejected | [Linear](https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this) |
| 2026-08-22 | [Open scope and AC ambiguity on the embedding fine-tuning rejection ticket](../../decisions/DEC-0006_embedding-finetuning-ticket-scope-ambiguity.md) | unresolved | [Linear](https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this) |
| 2026-08-22 | [Embedding fine-tuning rejection ticket: scope, AC, and success metrics finalized](../../decisions/DEC-0007_embedding-finetuning-ticket-scope-resolved.md) | superseded | [Linear](https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this) |

## Evidence
- [DEC-0002](../../decisions/DEC-0002_hybrid-retrieval-search-endpoint.md)
- [DEC-0004](../../decisions/DEC-0004_reject-custom-embedding-model-finetuning.md)
- [DEC-0006](../../decisions/DEC-0006_embedding-finetuning-ticket-scope-ambiguity.md)
- [DEC-0007](../../decisions/DEC-0007_embedding-finetuning-ticket-scope-resolved.md)

## Open Questions
- Is `hybrid-search` the right feature request for this work, or does it belong to an existing one? Created by an agent from decision DEC-0002 (meeting: healthcare-semantic-search-sprint-planning-2026-08-21); rename or merge if wrong.

**Resolved:**
- Where ABC-8's acceptance criteria belong, which chunker module the semantic-boundary chunking investment targets, whether there's a trigger for revisiting the fine-tuning rejection, and what success metric governs the chunking investment — resolved, see [DEC-0007](../../decisions/DEC-0007_embedding-finetuning-ticket-scope-resolved.md).

## Risks / Rejected Approaches
- Fine-tuning a custom clinical embedding model on the internal corpus this quarter was proposed and rejected: no labelled clinical relevance dataset exists to train against, fine-tuning on patient data would make the model itself regulated data (enlarging compliance scope), and the actual retrieval failures observed were lexical (fixed by hybrid retrieval) and chunking-related, not embedding-quality failures ([DEC-0004](../../decisions/DEC-0004_reject-custom-embedding-model-finetuning.md)).

## Relationships
**Depends On:** [pii-redaction](../pii-redaction/feature-request.md) — text must be redacted before it is embedded and indexed for this search to run over it.
**Related:** [clinician-search-ui](../clinician-search-ui/feature-request.md) — this endpoint is what the clinician-facing results interface calls.
**Related:** [search-audit-logging](../search-audit-logging/feature-request.md) — the endpoint is being built behind a flag and will not be enabled for real users until the query log retention policy is closed.
