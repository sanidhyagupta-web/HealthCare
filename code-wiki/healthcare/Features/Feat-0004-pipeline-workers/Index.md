---
feat_id: Feat-0004
feature: pipeline-workers
type: backend-service
domain: document-processing
criticality: high
touched_paths:
  - workers/
  - queues/
  - ingestion/chunking/
  - ingestion/pii/
depends_on: [Feat-0003-document-ingestion, Feat-0002-document-indexing, Feat-0007-security-access-control, Feat-0008-storage-persistence, Feat-0001-ade-extraction-service]
consumed_by: [Feat-0006-streamlit-ui]
implements: []
tags: [async, workers, queue, pii, pipeline]
---

## Overview

| | |
|---|---|
| Type | backend-service |
| Package | `workers/` + `queues/` (plus `ingestion/chunking/` and `ingestion/pii/`, colocated under `ingestion/` but functionally part of this pipeline) |
| Path | `workers/*.py`, `queues/*.py` |
| Domain | Async, multi-stage document processing — the engine behind every status transition after `VALIDATED` |
| Last updated | initial scan |

## Domain Purpose

Runs the document all the way from "validated" to "searchable": parse → convert to markdown →
chunk → detect & mask PII → extract drug/ADE pairs → embed → keyword-index. Each stage is a
daemon-thread worker consuming its own in-process `queue.Queue`, so a slow or failing stage never
blocks intake, only its own downstream progress.

## Entities Owned

None directly — writes to [[Feat-0003-document-ingestion]]'s `document_registry` and
`chunk_registry` via `ingestion/registry.py`, and to [[Feat-0002-document-indexing]]'s vector/keyword
stores. This feature is the connective tissue between those two, not an owner of persisted state
itself.

## Status / State Machine

Owns every transition from `PARSING` through `INDEXED` (see full table in
[[Schemas/schemas.md#document_registry]]). Each worker updates one link:

| Worker | Reads from | Writes to | Transition it drives |
|---|---|---|---|
| `ParserWorker` | `parsing_queue` | `markdown_queue` | `VALIDATED → PARSING → PARSED` |
| `MarkdownWorker` | `markdown_queue` | `chunking_queue` | `PARSED → MARKDOWN_READY` |
| `ChunkingWorker` | `chunking_queue` | `pii_queue` | `MARKDOWN_READY → CHUNKED` (or `→ DUPLICATE`, terminal, if every chunk is already known) |
| `PiiWorker` | `pii_queue` | `extraction_queue` | `CHUNKED → PII_PROCESSED` |
| `ExtractionWorker` | `extraction_queue` | `embedding_queue` **and** `keyword_queue` (fan-out) | `PII_PROCESSED → EXTRACTED` |
| `EmbeddingWorker` | `embedding_queue` | — | `EXTRACTED → EMBEDDED → INDEXED` |
| `KeywordIndexWorker` | `keyword_queue` | — | no registry status update |

## Invariants

- Retry budget is 3 attempts (`BaseWorker`, `max_retries` config) — beyond that, the message goes
  to the dead-letter queue (`queues/dlq.py`) rather than being dropped silently.
- PII must be detected, encrypted, and redacted before a chunk is embedded or keyword-indexed —
  enforced by pipeline ordering (`pii_queue` sits before `extraction_queue`/`embedding_queue`),
  not by a runtime check in the later workers.
- OCR quality below the configured threshold fails the document (`FAILED` + DLQ) rather than
  silently indexing low-confidence text.
- `run.py::recover_stuck_docs()` re-enqueues documents found in `PII_PROCESSED` or `EXTRACTED`
  status at startup, to recover from a crash mid-pipeline — but **only** those two statuses; a
  crash during `PARSING`, `MARKDOWN_READY`, or `CHUNKED` is not auto-recovered.

## Access Control

**Model**: department-based RBAC is *embedded* here, not enforced here. `PiiWorker` calls
`get_allowed_roles(department)` ([[Feat-0007-security-access-control]]) and writes the resulting
role list into each chunk's `allowed_roles` metadata — the actual filtering happens later, at
query time, in [[Feat-0007-security-access-control]]'s `filter_results_by_role()`.

| Action | Access Condition | Enforced In |
|---|---|---|
| embedding `allowed_roles` metadata | department → role map, no per-document override | `workers/pii_worker.py` calling `ingestion/metadata/rbac_policy.py` |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Max 3 retries per stage before dead-lettering | `workers/base_worker.py` | HIGH |
| BR-02 | OCR quality below threshold → `FAILED` + DLQ, never silently indexed | `workers/parser_worker.py` | CRITICAL |
| BR-03 | Chunk dedup by SHA256 hash; duplicate chunks are skipped, not re-embedded | `workers/chunking_worker.py` | HIGH |
| BR-04 | If every chunk in a document is a duplicate, the whole document is marked `DUPLICATE` (terminal) | `workers/chunking_worker.py` | MEDIUM |
| BR-05 | Plaintext PHI is never written to disk — chunks travel inline in queue messages until the PII stage encrypts/redacts them | `workers/pii_worker.py` | CRITICAL |
| BR-06 | Extraction (ADE) failures never block embedding/keyword-indexing — the pipeline degrades gracefully rather than stalling the whole document | `workers/extraction_worker.py` | HIGH |
| BR-07 | Unknown department raises `ValueError` rather than defaulting to an open role set | `ingestion/metadata/rbac_policy.py` | CRITICAL |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| [[Feat-0001-ade-extraction-service]] | `ExtractionWorker`, per sentence | `HTTP POST http://localhost:8001/extract`; connection errors/timeouts logged and skipped, not retried |
| S3 | `ParserWorker`, `MarkdownWorker`, `ChunkingWorker` | download raw/parsed content, upload processed artifacts |
| [[Feat-0002-document-indexing]] | `EmbeddingWorker`, `KeywordIndexWorker`, `PiiWorker` | writes embeddings, keyword-index entries, and PII-entity hash entries |

## Safe vs Dangerous Changes

### Safe
- Adding a new worker stage at the end of the pipeline (after `KeywordIndexWorker`) that doesn't change existing queue message shapes

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing a queue message's dict shape (e.g. renaming a key `ExtractionWorker` writes) | Breaks both `EmbeddingWorker` and `KeywordIndexWorker`, which both read the same fanned-out message | High-risk coupling — see dependency-mapper's flagged risk |
| Changing `max_retries` or DLQ behavior | Silently changes how many transient failures get lost vs. retried | 
| Skipping the PII stage for any document type | Breaks the "plaintext PHI never on disk" invariant | 

### Human Escalation Required
- Extending `recover_stuck_docs()` to cover earlier pipeline stages (`PARSING`, `MARKDOWN_READY`, `CHUNKED`) — currently a real gap in crash recovery.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| OCR quality insufficient | document → `FAILED`, sent to DLQ | `parser_worker.py` quality check |
| Document/chunk not found during a status update | `RegistryError` | concurrent deletion or id mismatch |
| Invalid state transition | `RegistryError` | caller violated the state machine |
| Unknown department | `ValueError` | department not in the fixed map |
| Max retries exceeded | message routed to DLQ, logged at ERROR | `base_worker.py` |
| ADE API unreachable/timeout | extraction skipped for that sentence, pipeline continues | `extraction_worker.py` catches and logs |
| Queue reaches `maxsize=500` | `queue.Full` — **not caught**, would crash the producing worker | `queues/queue_client.py` |

## Testing Expectations

*Open question: no dedicated `tests/unit/` file scans `workers/` or `queues/` directly — coverage
is indirect via [[Feat-0003-document-ingestion]]'s `test_bulk_ingestion.py` (which mocks the queue
handoff) and [[Feat-0005-semantic-search-qa]]'s RBAC tests (which exercise the metadata this
pipeline produces, not the pipeline itself).*

## Key Files

- `workers/base_worker.py` — shared retry/poll/DLQ-routing logic every worker inherits
- `workers/parser_worker.py` — file download, doc-type detection, OCR + quality gate
- `workers/pii_worker.py` — PII detection, encryption, redaction, RBAC metadata embedding
- `workers/extraction_worker.py` — sentence splitting, ADE API calls, fan-out to two queues
- `workers/embedding_worker.py`, `workers/keyword_index_worker.py` — parallel terminal stages
- `queues/queue_client.py` — queue definitions, timeout-based polling
- `queues/dlq.py` — dead-letter persistence to `dlq.log` (JSON lines)
- `run.py` — worker lifecycle, startup, `recover_stuck_docs()`

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0004-pipeline-workers | touching any worker stage, queue message shapes, retry/DLQ behavior, or crash recovery |

## Forbidden Patterns

- Never let a worker write a chunk past the PII stage without it having gone through `PiiWorker`'s masking/encryption first — every later stage assumes it already has.
- Never change one worker's output message shape without checking every worker that reads from the queue it writes to (see the `ExtractionWorker` fan-out coupling above).

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| In-process `queue.Queue` instead of a message broker (SQS/Kafka/RabbitMQ) | Simplicity for a single-process prototype deployment | Understanding this means the whole pipeline dies with the process — no durability across restarts except via `recover_stuck_docs()`'s partial coverage |
| Extraction failures are non-fatal to the rest of the pipeline | An ADE model hiccup shouldn't block search/indexing, which are the primary product value | Changing this trades pipeline resilience for extraction completeness — should be a deliberate product decision, not incidental |

## Known Gaps

- No circuit breaker/backoff for the ADE API — every transient failure permanently loses that sentence's extraction (no retry queue for extraction specifically).
- `queue.Full` (at `maxsize=500`) is unhandled and would crash the producing worker under load.
- DLQ is file-only — no automated replay; an operator must manually read `dlq.log` and re-drive documents.
- Crash recovery (`recover_stuck_docs()`) does not cover `PARSING`/`MARKDOWN_READY`/`CHUNKED` — a crash during those stages leaves the document stuck until manually retried.
