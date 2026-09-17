---
feat_id: Feat-0002
feature: document-ingestion-pipeline
type: backend-service
domain: document-ingestion
criticality: high
touched_paths:
  - app/
  - ingestion/
  - storage/
depends_on: [Feat-0001, Feat-0004, Feat-0007]
consumed_by: [Feat-0001, Feat-0005, Feat-0006]
implements: []
tags: [ingestion, http-api, file-upload, rbac]
---

## Overview

| Field | Value |
|---|---|
| Type | backend-service |
| Package | `app/`, `ingestion/`, `storage/` |
| Path | `app/*.py`, `ingestion/**/*.py`, `storage/*.py` |
| Domain | document-ingestion |
| Last updated | 2026-09-17 |

## Domain Purpose

Accepts a document (single upload or batch), validates it's a legitimate, safe healthcare
record, and gets it durably stored and queued for processing — this is the front door for
every document that ends up searchable in the system, and it owns the document/chunk registry
and department→role access policy that the rest of the system reads.

## Entities Owned

| Entity | Represents |
|---|---|
| [document_registry](../../Schemas/schemas.md#document_registry) | One row per ingested document — status, retry count, uploader, S3 location |
| [chunk_registry](../../Schemas/schemas.md#chunk_registry) | One row per unique chunk — dedup tracking via content hash |

## Status / State Machine

Owns the canonical `DocStatus` state machine (`ingestion/state_machine.py`) that Feat-0001's
workers execute:

`UPLOADED → VALIDATED → PARSING → PARSED → MARKDOWN_READY → CHUNKED → PII_PROCESSED → EXTRACTED → EMBEDDED → INDEXED`,
with `DUPLICATE` reachable from `CHUNKED` and `FAILED` reachable from any non-terminal state
(then re-enterable back to `PARSING`).

See Feat-0001's own State Machine table for the full per-transition trigger list — this
feature defines the transitions (`VALID_TRANSITIONS`), Feat-0001's workers execute them.

## Invariants

- A document's `department` is set at ingest and is immutable — RBAC downstream is entirely a
  function of this value via `ingestion/metadata/rbac_policy.py`.
- Only files with a supported extension (`.pdf`, `.txt`, `.dcm`), under 50MB, without an
  executable file signature, are accepted.
- A document with the same filename cannot be re-ingested while an existing entry for it is in
  a non-terminal, non-`DUPLICATE` status.
- Plaintext PII never touches local disk after the raw file is uploaded to S3 — the raw
  temp-file download is deleted in a `finally` block.

## Access Control

**Model**: role-based, checked against a fixed allowlist for ingestion, separate from the
department→role mapping used for read access at query time (Feat-0004/Feat-0005 own read-side
enforcement; this feature owns write-side).

| Action | Access Condition | Enforced In |
|---|---|---|
| Submit document (single or bulk) | caller's `role` ∈ `{doctor, nurse, admin}` | `ingestion/metadata/rbac_policy.py:get_ingest_allowed_roles()`, checked at `app/main.py:168` |
| Attach `allowed_roles` metadata to a chunk | `department` must be a known key in `_DEPARTMENT_ROLES`, else `ValueError` | `ingestion/metadata/rbac_policy.py:get_allowed_roles()` |

**CRITICAL finding**: `POST /ingest/bulk`'s `role` is read from a plain HTTP header
(`Header(...)` in FastAPI) with no session, token, or signature behind it — see
`security.md`'s `AUTH_MECHANISM` note. Any caller can set `role: admin` and pass this check.
Treat this endpoint as unauthenticated when reviewing changes to it.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Only `.pdf`/`.txt`/`.dcm` accepted; reject executable headers (MZ/ELF/shebang), >50MB, empty files | `ingestion/validator.py:42-65` | CRITICAL |
| BR-02 | Max 50 files per bulk-ingest request | `app/main.py:171-173` | MEDIUM |
| BR-03 | Duplicate filename (non-terminal existing doc) is rejected, not re-queued | `ingestion/registry.py:is_duplicate_document()` | HIGH |
| BR-04 | Unknown `department` value raises `ValueError` at ingest rather than silently producing a zero-access chunk later | `ingestion/metadata/rbac_policy.py:27-31` | CRITICAL |
| BR-05 | Exactly one `BULK_INGEST_SUBMITTED` audit event per batch request, regardless of per-file outcome | `app/main.py:188-192` | MEDIUM |
| BR-06 | A single file's failure in a bulk batch never blocks the rest of the batch | `app/main.py:_process_single_upload_bytes` (never raises — always returns a rejected entry) | HIGH |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| S3 (`storage/s3_client.py`) | Every ingest call | Raw file uploaded with KMS encryption before local temp copy is deleted |
| Local filesystem watcher (`ingestion/watcher.py`) | Polls `settings.raw_dir` subfolders every 5s | Auto-ingests files dropped into watched directories, same path as the Python API |
| `queues.parsing_queue` (Feat-0001) | Successful validation + S3 upload | Enqueues the document for worker processing |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|---|---|---|---|---|
| POST | /ingest/bulk | `role` HTTP header, checked against an allowlist — **not independently authenticated**, see Access Control | External HTTP clients (not the Streamlit UI — see Feat-0006's open question) | Batch-uploads up to 50 files, returns per-file queued/rejected status |

## Safe vs Dangerous Changes

### Safe
- Adding a new supported file extension to `ingestion/validator.py` (with matching parser support).
- Adding a new department to `_DEPARTMENT_ROLES`.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing `VALID_TRANSITIONS` | Breaks every worker in Feat-0001 that calls `update_status()` | This is the single source of truth for the pipeline's state machine |
| Removing/renaming a `_DEPARTMENT_ROLES` key | Silently strips read access from existing chunks in that department, or raises `ValueError` at next ingest | `allowed_roles` is baked into chunk metadata at ingest time — not recomputed retroactively |
| Adding auth middleware to `/ingest/bulk` | Could change behavior expected by any existing external caller | Coordinate before closing the header-trust gap noted above |

### Human Escalation Required
- Any fix to the unauthenticated `role` header on `/ingest/bulk` — this is a real access-control gap, not a stylistic one; closing it changes the contract for whoever calls this endpoint today.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Invalid/oversized/executable file | `ValueError` (single) / `rejected` entry (bulk) | `ingestion/validator.py` |
| S3 credentials unavailable/expired | `ValueError` with AWS SSO login hint | `app/main.py:65-69` — note: this message includes an internal AWS profile name, a minor information-exposure smell |
| Caller role not in ingest allowlist | HTTP 403 | `app/main.py:168-169` |
| >50 files in one batch | HTTP 422 | `app/main.py:171-173` |
| Unknown department | `ValueError` at PII stage (Feat-0001), not at ingest | `ingestion/metadata/rbac_policy.py:30` — *open question: should this validate at ingest time instead of failing later in the pipeline?* |

## Testing Expectations

- `tests/unit/test_bulk_ingestion.py` exists and covers bulk-ingest behavior.
- Validation edge cases (executable signatures, oversized files, unknown departments) should have explicit tests — not confirmed present beyond what `test_bulk_ingestion.py` covers.

## Forbidden Patterns

- Never persist a raw uploaded file to local disk without deleting it once uploaded to S3.
- Never accept a document without validating extension, size, and file signature first.
- Never add a new `DocStatus` value without also updating `run.py:recover_stuck_docs()`'s recoverable-status list (see Feat-0001).

## Key Files

- `app/main.py` — `ingest_document()` Python API, `POST /ingest/bulk`, `_process_single_upload_bytes` helper
- `ingestion/registry.py` — document/chunk registration, status transitions, duplicate detection
- `ingestion/state_machine.py` — `DocStatus` enum, `VALID_TRANSITIONS`
- `ingestion/validator.py` — file validation (extension, size, magic bytes, DICOM)
- `ingestion/watcher.py` — filesystem watcher, alternate ingest entry point
- `ingestion/metadata/rbac_policy.py` — `_DEPARTMENT_ROLES`, `_INGEST_ALLOWED_ROLES` — single source of truth
- `ingestion/pii/`, `ingestion/parsers/`, `ingestion/markdown/`, `ingestion/ocr/`, `ingestion/chunking/` — stage implementations invoked by Feat-0001's workers
- `storage/s3_client.py` — S3 upload/download/delete, KMS encryption

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0001 (Async Processing Workers) | changing anything a worker reads/writes (state machine, S3 key layout, chunk registry) |
| Feat-0004 (Security & Access Control) | changing ingest-time auth or department/role policy |

| Workflow | Sections to load |
|---|---|
| Add a new ingest endpoint | Access Control, Business Rules, API Endpoints |
| Add a supported file type | Business Rules, Key Files, Safe vs Dangerous Changes |
