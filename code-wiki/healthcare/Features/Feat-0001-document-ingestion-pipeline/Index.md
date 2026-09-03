---
feat_id: Feat-0001
feature: document-ingestion-pipeline
type: backend-service
domain: healthcare-document-ingestion
criticality: high
touched_paths:
  - app/
  - ingestion/
  - workers/
  - queues/
  - storage/
  - monitoring/
  - db/
  - run.py
depends_on: [Feat-0005, Feat-0002]
consumed_by: [Feat-0004]
implements: []
tags: [ingestion, pipeline, pii, rbac]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | (single package) | `app/`, `ingestion/`, `workers/`, `queues/`, `storage/`, `monitoring/`, `db/` | Healthcare document ingestion | 2026-09-03 |

## Domain Purpose

Takes an uploaded medical document (PDF, scanned image, DICOM, or plain text) and turns it into
searchable, PII-redacted, RBAC-tagged chunks — validating, parsing/OCR'ing, chunking around
medical entities, detecting and encrypting PHI, extracting drug/adverse-event mentions, and
indexing the result for retrieval.

## Entities Owned

| Entity | Represents |
|---|---|
| [document_registry](../../Schemas/schemas.md#document_registry) | One row per uploaded document, tracking pipeline status end-to-end |
| [chunk_registry](../../Schemas/schemas.md#chunk_registry) | One row per deduplicated chunk produced from a document |

## Status / State Machine

| Status | Business Meaning | Can Transition To | Trigger |
|---|---|---|---|
| UPLOADED | Registered, not yet checked | VALIDATED | `ingest_document()` / `_process_single_upload_bytes()` |
| VALIDATED | Passed validation, uploaded to S3 | PARSING | enqueued to `parsing_queue` |
| PARSING | ParserWorker picked it up | PARSED / FAILED | parse/OCR completes or fails |
| PARSED | Text extracted | MARKDOWN_READY | MarkdownWorker runs |
| MARKDOWN_READY | Structured as Markdown | CHUNKED | ChunkingWorker runs |
| CHUNKED | Chunks produced | PII_PROCESSED / DUPLICATE | all chunks duplicate → DUPLICATE (terminal); else PiiWorker runs |
| PII_PROCESSED | PII detected, encrypted, redacted | EXTRACTED | ExtractionWorker runs |
| EXTRACTED | Drug/ADE extraction attempted (best-effort) | EMBEDDED | EmbeddingWorker runs |
| EMBEDDED | Vector-indexed | INDEXED | (also triggers keyword indexing) |
| INDEXED | Fully searchable | — (terminal) | — |
| FAILED | Any state → FAILED on unrecoverable error | PARSING (retry only) | worker exception after `max_retries`, or OCR quality below threshold |
| DUPLICATE | All produced chunks already exist | — (terminal) | ChunkingWorker finds zero new chunks |

- `recover_stuck_docs()` (`run.py`) re-enqueues documents left in `PII_PROCESSED` or `EXTRACTED`
  when the process last stopped, since in-memory queues don't survive a restart. **Gap:** it does
  *not* cover `PARSING`, `PARSED`, `MARKDOWN_READY`, or `CHUNKED` — a crash during those stages
  loses the in-flight work permanently (open question below).

## Invariants

- `chunk_registry.chunk_hash` is unique — prevents the same content being embedded/indexed twice.
- A document cannot leave a terminal state (`FAILED`, `DUPLICATE`, `INDEXED`) except `FAILED →
  PARSING` on retry.
- Plaintext PII must never persist on local disk: chunk text stays in-memory/in-queue-message
  until `PiiWorker` redacts it; only the redacted form is ever written to
  `data/processed/redacted/{doc_id}/redacted_chunks.json`.

## Access Control

**Model**: RBAC (role-based) at the ingest boundary; the FastAPI endpoint has **no
authentication of its own** — see the gap called out below and in
[Feat-0005](../Feat-0005-security-access-control/Index.md).

| Action | Access Condition | Enforced In |
|---|---|---|
| `POST /ingest/bulk` | caller's `role` header ∈ `{doctor, nurse, admin}` | `ingestion/metadata/rbac_policy.py:get_ingest_allowed_roles()`, checked at `app/main.py:168` |
| Department tagging at ingest | department must be a known key or ingest fails loudly | `ingestion/metadata/rbac_policy.py:get_allowed_roles()` raises `ValueError` on unknown department |

## Business Rules

| BR | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Only `.pdf`, `.txt`, `.dcm` accepted; executable/script magic bytes rejected | `ingestion/validator.py` | CRITICAL |
| BR-02 | Max file size 50MB | `app/config.py` (`max_file_size_bytes`) | HIGH |
| BR-03 | Duplicate filename (non-failed/non-duplicate status) is rejected | `ingestion/registry.py:is_duplicate_document` | MEDIUM |
| BR-04 | Chunks deduplicated by SHA-256; all-duplicate document → terminal `DUPLICATE` | `workers/chunking_worker.py` | HIGH |
| BR-05 | Medical entities (medication+dosage, vitals, labs, ICD-10) must not be split across chunk boundaries | `ingestion/chunking/entity_preserving_chunker.py` | HIGH |
| BR-06 | Only `POST /ingest/bulk` — caller's `role` header trusted with no identity verification | `app/main.py:156,168` | CRITICAL — see [Feat-0005](../Feat-0005-security-access-control/Index.md) |
| BR-07 | Bulk ingest caps at 50 files/request; per-file failure doesn't block the rest of the batch | `app/main.py:171` | MEDIUM |
| BR-08 | Worker failure retried inline up to `max_retries` (3), then routed to DLQ | `workers/base_worker.py` | HIGH |
| BR-09 | OCR output below confidence threshold (default 0.40) fails the document rather than indexing low-quality text | `workers/parser_worker.py`, `app/config.py:ocr_confidence_threshold` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| AWS S3 (+ KMS) | every upload | raw file and intermediate artifacts stored encrypted; `storage/s3_client.py` |
| LLM / ADE Extraction Service (Feat-0002) | `ExtractionWorker` per sentence | `POST http://localhost:8001/extract` — no auth, 30s timeout, failure degrades gracefully (extraction skipped, pipeline continues) |
| In-memory queues (`queues/`) | every stage transition | see Async Processes — this is the pipeline's backbone, not a message broker |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|---|---|---|---|---|
| POST | `/ingest/bulk` | client-supplied `role` header, **unverified** | [Feat-0004](../Feat-0004-healthcare-semantic-search-ui/Index.md) `bulk_upload_page.py` | Batch-upload up to 50 files |
| — | `ingest_document()` (Python API, not HTTP) | caller-supplied `uploader_id`, no verification | Feat-0004 `upload_page.py` | Single-file ingest |

## Safe vs Dangerous Changes

### Safe
- Adding a new supported file extension to `ingestion/validator.py` (with corresponding parser support).
- Adding a new `DocStatus` terminal state, as long as `recover_stuck_docs()` and the state machine transition table are updated together.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing `redacted_chunks.json` shape | Breaks ExtractionWorker, EmbeddingWorker, KeywordIndexWorker | All three read this file; no schema versioning |
| Removing/renaming `get_ingest_allowed_roles()` | Silently opens ingest to any role | It is the sole enforcement point (see Feat-0005) |
| Changing queue message shape for any queue | Breaks the downstream worker silently, no compile-time check | In-memory queues carry untyped dicts |

### Human Escalation Required
- Adding real authentication to `POST /ingest/bulk` — this is a cross-cutting security decision, not a local one (see Feat-0005 CRITICAL gap).

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Unsupported extension / oversized / malicious header | 400 (bulk) or `ValueError` (single) | `ingestion/validator.py` |
| S3 upload fails (bad/expired credentials) | `ValueError` with SSO login instructions | `app/main.py` catches `TokenRetrievalError`/`NoCredentialsError` |
| Duplicate filename | rejected entry in bulk response | `ingestion/registry.py:is_duplicate_document` |
| OCR confidence below threshold | document `FAILED` | `workers/parser_worker.py` |
| ADE extraction service unreachable | extraction skipped, pipeline continues (graceful degradation) | `workers/extraction_worker.py` |
| Worker exception exceeds `max_retries` | message routed to DLQ, logged to `dlq.log` | `workers/base_worker.py` |

## Testing Expectations

- `tests/unit/test_bulk_ingestion.py` covers `POST /ingest/bulk` RBAC (role accepted/rejected) with S3/registry/audit mocked via `monkeypatch`/`unittest.mock`.
- `tests/unit/test_dicom_parser.py` covers DICOM parsing/markdown conversion in isolation.
- No test coverage found for: state-machine transition violations, OCR-quality failure path, `recover_stuck_docs()`.

## Forbidden Patterns

- Never write unredacted chunk text to local disk — PiiWorker is the only stage permitted to
  persist chunk content, and only after redaction.
- Never bypass `ingestion/metadata/rbac_policy.py` for department/role lists — it is documented as
  the single source of truth (see its own docstring).

## Key Files

- `app/main.py` — FastAPI app, `POST /ingest/bulk`, `ingest_document()`, `_process_single_upload_bytes()`
- `run.py` — worker orchestration entrypoint, `recover_stuck_docs()`
- `ingestion/registry.py` — registration, status transitions, duplicate/chunk-hash dedup
- `ingestion/state_machine.py` — `DocStatus` enum and legal transitions
- `ingestion/validator.py` — file validation
- `ingestion/chunking/entity_preserving_chunker.py` — medical-entity-aware chunking
- `ingestion/pii/pii_detector.py`, `pii_redactor.py` — PII detection/redaction (ingest-time)
- `ingestion/metadata/rbac_policy.py` — department↔role policy, ingest-allowed roles
- `workers/*.py` — one file per pipeline stage (parser, markdown, chunking, pii, extraction, embedding, keyword_index), plus `base_worker.py` for shared retry/DLQ logic
- `queues/queue_client.py`, `queues/dlq.py` — in-memory queue + dead-letter handling
- `storage/s3_client.py` — S3/KMS upload/download
- `db/models.py` — `DocumentRegistry`, `ChunkRegistry` (also `AuditLog`, owned by Feat-0005)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0001 | touching upload, validation, chunking, PII redaction (ingest-time), or worker/queue logic |
| Feat-0005 | touching auth, RBAC policy enforcement, encryption, or audit logging |
| Feat-0002 | touching the ADE extraction call or its request/response shape |

*Open question: should `recover_stuck_docs()` also cover `PARSING`/`PARSED`/`MARKDOWN_READY`/`CHUNKED`, or is losing that in-flight work on restart an accepted tradeoff?*

*Open question: `monitoring/tracing.py` references `settings.langsmith_api_key` and
`settings.langsmith_project`, but `app/config.py`'s `Settings` dataclass defines neither field —
is this dead code, or a field that was removed from `Settings` without updating `tracing.py`?*
