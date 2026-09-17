---
feat_id: Feat-0007
feature: workers
type: backend-service
domain: async-pipeline-execution
criticality: high
touched_paths:
  - workers/base_worker.py
  - workers/pii_worker.py
  - workers/parser_worker.py
  - workers/extraction_worker.py
  - workers/chunking_worker.py
  - workers/embedding_worker.py
  - workers/keyword_index_worker.py
  - workers/markdown_worker.py
  - queues/queue_client.py
  - queues/dlq.py
depends_on: [ingestion, platform, indexing, security, llm]
consumed_by: [ui, app]
implements: []
tags: [async, queue, threading, retry, dlq]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | `workers` (+ `queues`) | `workers/`, `queues/` | Async execution of every ingestion pipeline stage | 2026-09-17 (initial scan) |

## Domain Purpose

Seven daemon-thread workers, each consuming one in-process queue, that carry a document through
parsing → markdown → chunking → PII redaction → drug/ADE extraction → embedding + keyword indexing.
Started by `scripts/start_workers.py`, not by [[app]] itself.

## Invariants

- Plaintext PII exists only in-memory between `ChunkingWorker` (produces chunks inline in the queue
  message) and `PiiWorker` (encrypts + redacts) — never written to disk in between.
- Every stage transition goes through [[ingestion]]'s `can_transition()` guard; a worker cannot move
  a document to a non-adjacent status.
- Each worker is a `daemon=True` thread — the process exits immediately when the main thread ends,
  mid-message work is not guaranteed to finish.
- Queues are stdlib `Queue.Queue`, `maxsize=500`, thread-safe by construction.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Max 3 retries (`settings.max_retries`) before a message routes to the DLQ | `workers/base_worker.py:32-36` | MEDIUM |
| BR-02 | OCR confidence below threshold fails the document and DLQs it | `workers/parser_worker.py:64-67,75-78` | HIGH |
| BR-03 | Startup recovery only re-enqueues documents stuck in `PII_PROCESSED` (the one state whose intermediate artifact — `redacted_chunks.json` — survives a crash); any other stuck state stays stuck | `scripts/start_workers.py:29-31` | MEDIUM |
| BR-04 | `ExtractionWorker`'s ADE API call failures are swallowed — logged WARN, returns `(None, None)`, no retry, no DLQ | `workers/extraction_worker.py:61-66` | MEDIUM |
| BR-05 | `KeywordIndexWorker` does not update document status — `EmbeddingWorker` already transitioned it to `EMBEDDED`/`INDEXED` | `workers/keyword_index_worker.py` (absence) | LOW |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| [[llm]] `ade_api` (`POST /extract`) | `ExtractionWorker`, per sentence | HTTP call to `ADE_API_URL`; failure is silent (see BR-04) |
| S3 ([[platform]]) | `ParserWorker`, `MarkdownWorker`, `ChunkingWorker` | download/upload of raw, parsed, and markdown artifacts |
| Chroma / BM25 ([[indexing]]) | `EmbeddingWorker`, `KeywordIndexWorker` | index writes |

## Safe vs Dangerous Changes

### Safe
- Adding a new worker stage as long as it consumes/produces via the existing `QueueClient` pattern.
- Tuning `max_retries`/`queue_max_size`.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing the message shape any worker enqueues | Breaks the next worker in the chain silently at runtime | No schema validation between stages — a dict-shape typo is invisible until the consumer crashes |
| Extending crash-recovery to more intermediate states | Could re-process partially-written artifacts | Currently only `PII_PROCESSED` is recoverable because its artifact (`redacted_chunks.json`) is durable; other stages' intermediate state is not |
| Changing `can_transition()`'s allowed transitions (in [[ingestion]]) without checking every worker | Workers could get stuck unable to advance status | Every worker calls `update_status()` assuming today's transition table |

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Any worker exception | retry_count incremented, re-queued or DLQ'd on exhaustion | `workers/base_worker.py:28-38` |
| ADE API unreachable | extraction silently skipped for that sentence | `workers/extraction_worker.py:61-63` |
| No DLQ configured | message logged ERROR and dropped | `queues/queue_client.py:32-34` |
| `redacted_chunks.json` missing on crash-recovery | error logged, document stays stuck in `PII_PROCESSED` | `scripts/start_workers.py:51-56` |

## Testing Expectations

- No worker-specific unit tests were found in `tests/unit/` — coverage for pipeline behavior comes
  from `tests/unit/test_bulk_ingestion.py` exercising the ingest→enqueue boundary, not the workers
  themselves. *Open question: is there any test that runs a message through an actual worker
  instance?*

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| In-process `Queue.Queue` rather than an external broker (SQS/RabbitMQ/Redis) | Simplicity for a single-process deployment | Understanding this means the whole pipeline is lost on process restart unless recovery logic (`_recover_stuck_docs`) covers the state a document was in |

## Forbidden Patterns

- Never write a worker that skips `update_status()` after a stage completes — the state machine is
  the only source of truth for what's happened to a document.
- Never assume a downstream worker will validate the message shape — mismatches fail at the consumer with no upstream signal.

## Key Files

- `workers/base_worker.py` — shared retry/DLQ/threading framework
- `workers/parser_worker.py`, `markdown_worker.py`, `chunking_worker.py`, `pii_worker.py`, `extraction_worker.py`, `embedding_worker.py`, `keyword_index_worker.py` — one per pipeline stage
- `queues/queue_client.py` — thread-safe queue wrapper with DLQ routing
- `queues/dlq.py` — dead-letter queue, JSON-log-persisted
- `scripts/start_workers.py` — orchestration, graceful shutdown, crash recovery

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0007-workers | touching any pipeline stage's async execution, retry, or DLQ behavior |

| Workflow | Sections to load |
|---|---|
| Debugging a document stuck at a status | Known Error Scenarios, Business Rules BR-03 |
| Adding a new pipeline stage | Architectural Decisions, Key Files, then the adjacent worker's file as a template |
