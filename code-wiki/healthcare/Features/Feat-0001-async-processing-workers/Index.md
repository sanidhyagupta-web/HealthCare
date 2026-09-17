---
feat_id: Feat-0001
feature: async-processing-workers
type: backend-service
domain: document-processing
criticality: high
touched_paths:
  - workers/
  - queues/
depends_on: [Feat-0002, Feat-0003, Feat-0004, Feat-0005, Feat-0007]
consumed_by: [Feat-0002, Feat-0006]
implements: []
tags: [pipeline, async, queue-consumer]
---

## Overview

| Field | Value |
|---|---|
| Type | backend-service |
| Package | `workers/`, `queues/` |
| Path | `workers/*.py`, `queues/*.py` |
| Domain | document-processing |
| Last updated | 2026-09-17 |

## Domain Purpose

Turns a validated, uploaded document into a searchable, access-controlled, PII-safe chunk in
the vector and keyword indexes — the multi-stage transformation is long enough (parse → OCR →
markdown → chunk → redact PII → extract drug/ADE data → embed → index) that it runs as a chain
of independent, retryable stages rather than one long request.

## Invariants

- Every document that enters this pipeline has already passed file validation (owned by Feat-0002) — workers do not re-validate.
- Status transitions follow the state machine defined in Feat-0002; a worker never sets a status outside `VALID_TRANSITIONS`.
- Chunk hash is globally unique — no two chunks with identical content coexist in `chunk_registry`.
- No chunk reaches the embedding/keyword indexes (Feat-0005) without having passed through PII detection and redaction first.
- PHI is encrypted immediately on detection (`security.encryption`, Feat-0004) and never appears in plaintext in a searchable index.
- On any worker exception, the message retries up to `settings.max_retries` (default 3), then moves to the DLQ — no message is silently dropped.

## Status / State Machine

Workers drive the document through the state machine owned by Feat-0002 (`ingestion/state_machine.py`); this feature only executes the transitions, it does not define them.

| Status | Business Meaning | Can Transition To | Trigger |
|---|---|---|---|
| PARSING → PARSED | Raw file text/OCR extracted | MARKDOWN_READY | `ParserWorker.process` |
| PARSED → MARKDOWN_READY | Text restructured to markdown | CHUNKED | `MarkdownWorker.process` |
| MARKDOWN_READY → CHUNKED | Entity-preserving chunking done | PII_PROCESSED, DUPLICATE | `ChunkingWorker.process` |
| CHUNKED → PII_PROCESSED | PII detected, redacted, encrypted, RBAC metadata attached | EXTRACTED | `PiiWorker.process` |
| PII_PROCESSED → EXTRACTED | Drug/ADE extraction via LLM Extraction (Feat-0003) | EMBEDDED | `ExtractionWorker.process` |
| EXTRACTED → EMBEDDED → INDEXED | Embeddings generated, upserted to Chroma; keyword index updated | *(terminal)* | `EmbeddingWorker.process` (sets both) |
| any non-terminal → FAILED | Unhandled exception in a worker | PARSING (manual/DLQ replay) | worker exception, `retry_count >= max_retries` |

- On CHUNKED, if every chunk is a hash-duplicate of an existing one, the document goes to the terminal `DUPLICATE` state instead of `PII_PROCESSED`.

## Access Control

**Model**: none in this feature directly — workers run as trusted background processes with no per-caller identity. Access control is enforced upstream (ingest, Feat-0002) and downstream (query time, Feat-0004/Feat-0005), not inside the pipeline itself.

| Action | Access Condition | Enforced In |
|---|---|---|
| n/a | *None found — workers have no caller-facing access surface* | — |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | OCR confidence must exceed `settings.ocr_confidence_threshold` (default 0.40) or the document is marked FAILED | `workers/parser_worker.py:64-78` | HIGH |
| BR-02 | Chunk deduplication is global (across all documents), keyed on SHA256 content hash | `ingestion/registry.py:register_chunk()`, `db/models.py` (`chunk_hash` UNIQUE) | CRITICAL |
| BR-03 | Max 3 retries per message before routing to the DLQ | `workers/base_worker.py:30-36` | HIGH |
| BR-04 | PHI is encrypted before any database write, at the PII stage | `workers/pii_worker.py:48-56` | CRITICAL |
| BR-05 | Plaintext PII is never written to local disk — `redacted_chunks.json` (the only on-disk intermediate) contains redacted text only | `workers/chunking_worker.py:58-76`, `workers/pii_worker.py:84-88` | CRITICAL |
| BR-06 | ADE API (Feat-0003) unavailability is non-fatal — extraction is skipped for that sentence, pipeline continues | `workers/extraction_worker.py:61-66` | MEDIUM |
| BR-07 | Keyword indexing (`KeywordIndexWorker`) is fire-and-forget — no status update, no DLQ path on failure | `workers/keyword_index_worker.py` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| LLM Extraction API (Feat-0003, `POST http://localhost:8001/extract`) | `ExtractionWorker` processes a message | Each chunk's sentences POSTed one at a time (30s timeout); connection errors are logged and skipped, not retried |
| S3 (via Feat-0002's `storage/s3_client.py`) | Every worker stage except PiiWorker | Download raw/intermediate artifact, upload the stage's output |
| Chroma / BM25 (Feat-0005) | `EmbeddingWorker`, `KeywordIndexWorker` | Upsert chunk embeddings / keyword-index the chunk |

## Safe vs Dangerous Changes

### Safe
- Adding a new worker stage at the end of the chain (after `EmbeddingWorker`/`KeywordIndexWorker`).
- Tuning `settings.max_retries`, `settings.ocr_confidence_threshold`.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing `VALID_TRANSITIONS` (owned by Feat-0002) without updating every worker that calls `update_status()` | Workers raise `RegistryError` and go to DLQ on an invalid transition | All 6 workers assume the current transition set |
| Changing the `redacted_chunks.json` on-disk shape | Breaks `ExtractionWorker`/`EmbeddingWorker`/`KeywordIndexWorker`, which all read it by field name | No schema validation between PiiWorker's write and downstream reads |
| Adding a new terminal/intermediate status without updating `run.py:recover_stuck_docs()` | Documents stuck in the new status are never recovered on restart | `recover_stuck_docs()` hardcodes `PII_PROCESSED`/`EXTRACTED` as the only recoverable statuses |

### Human Escalation Required
- Any change to retry/DLQ semantics for PHI-bearing messages (compliance-relevant).

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| OCR confidence below threshold | Status → FAILED, sent to DLQ, reason "OCR quality insufficient" | `workers/parser_worker.py:64-78` |
| ADE API (Feat-0003) unreachable | No error surfaced — extraction skipped for that sentence | `workers/extraction_worker.py:61-66` |
| Invalid status transition | `RegistryError`, caught by `BaseWorker`, retried then DLQ'd | `ingestion/registry.py:update_status()` |
| Chunk hash collision | Chunk silently skipped (not counted as new); doc marked DUPLICATE if *all* chunks collide | `ingestion/registry.py:register_chunk()` |

## Testing Expectations

- Unit-level: retry/backoff logic in `BaseWorker`, OCR threshold branch, chunk-hash dedup branch.
- Integration-level: at least one full pipeline run (parsing → indexed) and one DLQ-routing run (forced failure past max retries).
- *Open question: no dedicated worker test files were found under `tests/unit/` — coverage for retry logic, OCR threshold, and DLQ routing could not be confirmed either way.*

## Forbidden Patterns

- Never write plaintext PII to disk — only redacted text may be persisted outside the queue message itself.
- Never call `update_status()` with a transition outside `VALID_TRANSITIONS` (Feat-0002) without updating the state machine first.
- Never let a worker crash silently — every exception must be caught by `BaseWorker`'s retry/DLQ path.

## Key Files

- `workers/base_worker.py` — shared poll/retry/DLQ loop every worker inherits
- `workers/parser_worker.py` — raw file → parsed text (typed PDF / scanned PDF+OCR / DICOM / plain text)
- `workers/markdown_worker.py` — parsed text → structured markdown
- `workers/chunking_worker.py` — markdown → entity-preserving chunks, hash-based dedup
- `workers/pii_worker.py` — PII detection, encryption, redaction, RBAC metadata attachment
- `workers/extraction_worker.py` — drug/ADE extraction via the LLM Extraction API (Feat-0003)
- `workers/embedding_worker.py` — embeddings + Chroma upsert
- `workers/keyword_index_worker.py` — BM25/OpenSearch indexing
- `queues/queue_client.py` — thread-safe in-memory queue with a max size (default 500)
- `queues/dlq.py` — dead-letter queue, persisted to `dlq.log`

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0002 (Document Ingestion Pipeline) | changing the state machine, validation, or S3 layout these workers depend on |
| Feat-0005 (Semantic Search & Indexing) | changing what `EmbeddingWorker`/`KeywordIndexWorker` write |
| Feat-0003 (LLM Extraction / Inference) | changing the `/extract` request/response contract |

| Workflow | Sections to load |
|---|---|
| Add a new worker stage | Status/State Machine, Key Files, Safe vs Dangerous Changes |
| Debug a stuck document | Status/State Machine, Known Error Scenarios, External Integrations |
