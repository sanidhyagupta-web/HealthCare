---
feat_id: Feat-0003
feature: document-ingestion
type: backend-service
domain: document-intake
criticality: high
touched_paths:
  - app/main.py
  - app/config.py
  - app/dependencies.py
  - ingestion/validator.py
  - ingestion/registry.py
  - ingestion/state_machine.py
  - ingestion/watcher.py
  - ingestion/parsers/
  - ingestion/ocr/
  - ingestion/markdown/
  - ingestion/metadata/
depends_on: [Feat-0007-security-access-control, Feat-0008-storage-persistence]
consumed_by: [Feat-0004-pipeline-workers, Feat-0006-streamlit-ui]
implements: []
tags: [ingestion, validation, rbac-policy, state-machine]
---

## Overview

| | |
|---|---|
| Type | backend-service |
| Package | `app/` + `ingestion/` (excluding `ingestion/chunking`, `ingestion/pii` — owned by [[Feat-0004-pipeline-workers]]'s scan target but physically colocated in `ingestion/`) |
| Path | `app/main.py`, `app/config.py`, `app/dependencies.py`, `ingestion/{validator,registry,state_machine,watcher}.py`, `ingestion/{parsers,ocr,markdown,metadata}/` |
| Domain | Document intake: validation, S3 upload, registry, RBAC policy for who may ingest |
| Last updated | initial scan |

## Domain Purpose

Accepts a document (single file via the Streamlit UI, or up to 50 files via the bulk HTTP
endpoint, or a filesystem watcher), validates it's a real, safe, supported file, uploads it
encrypted to S3, registers it in SQLite, and hands it off to the async worker pipeline
([[Feat-0004-pipeline-workers]]) for parsing/OCR/chunking/PII/embedding.

## Entities Owned

- `document_registry` → [[Schemas/schemas.md#document_registry]] — the document lifecycle record
- `chunk_registry` → [[Schemas/schemas.md#chunk_registry]] — chunk-level dedup record (registered here, populated further by [[Feat-0004-pipeline-workers]])

## Status / State Machine

See the full table in [[Schemas/schemas.md#document_registry]]. This feature owns the
`UPLOADED → VALIDATED` transition and the state-machine enforcement (`can_transition()`); every
later transition belongs to [[Feat-0004-pipeline-workers]].

## Invariants

- A document must pass `DocumentValidator.validate()` before it is ever uploaded to S3 or registered.
- S3 uploads are always encrypted — KMS if `KMS_KEY_ID` is configured, SSE-S3 fallback otherwise; there is no unencrypted upload path.
- `chunk_hash` uniqueness (DB-level `UNIQUE`) is the sole re-ingestion dedup mechanism.
- An invalid state transition raises `RegistryError` rather than silently applying — `can_transition()` is the only gate.

## Access Control

**Model**: role self-asserted by the caller, no signature/token verification.

| Action | Access Condition | Enforced In |
|---|---|---|
| `POST /ingest/bulk` | `role` HTTP header ∈ `{doctor, nurse, admin}` (`get_ingest_allowed_roles()`) | `app/main.py:168` |
| `ingest_document()` Python API (used by Streamlit) | none at this layer — relies on [[Feat-0006-streamlit-ui]]'s session gate having already run | `app/main.py:37` |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Only `doctor`, `nurse`, `admin` may submit documents for ingestion | `ingestion/metadata/rbac_policy.py::get_ingest_allowed_roles()`, checked in `app/main.py:168` | CRITICAL |
| BR-02 | Max file size 50 MB | `ingestion/validator.py`, `app/config.py::max_file_size_bytes` | HIGH |
| BR-03 | Only `.pdf`/`.txt`/`.text`/DICOM files accepted; executable magic bytes (`MZ`, `ELF`, shebang) rejected outright | `ingestion/validator.py` | CRITICAL |
| BR-04 | Bulk request capped at 50 files | `app/main.py:171` | MEDIUM |
| BR-05 | Duplicate filename (non-`FAILED`/non-`DUPLICATE` existing doc) is rejected before upload | `ingestion/registry.py::is_duplicate_document()`, checked `app/main.py:116` | MEDIUM |
| BR-06 | Document state transitions must follow the state machine — no skipping stages | `ingestion/registry.py::update_status()` via `can_transition()` | CRITICAL |
| BR-07 | One `BULK_INGEST_SUBMITTED` audit event per batch request, not one per file | `app/main.py:188` | LOW |
| BR-08 | One bad file in a bulk batch never blocks the others — `_process_single_upload_bytes()` catches everything and returns a rejected entry instead | `app/main.py` | HIGH |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| AWS S3 (+ KMS) | every accepted upload | raw bytes stored at `raw/{doc_id}/{filename}`, encrypted |
| filesystem watcher | polls `raw/{pdfs,scanned,text}/` every ~5s (configurable) | calls `ingest_document()` with `uploader_id="watcher"` for any new file |
| [[Feat-0004-pipeline-workers]] | after successful registration | `queues.parsing_queue.put({doc_id, raw_s3_key, file_suffix, original_filename, uploader_id, patient_id, department, retry_count: 0})` |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|---|---|---|---|---|
| POST | `/ingest/bulk` | `role` header, unsigned/self-asserted | [[Feat-0006-streamlit-ui]]'s `bulk_upload_page.py` calls the Python function directly rather than this HTTP route in-process — *open question: is this endpoint reachable by anything other than the Streamlit process itself?* | up to 50 files, returns per-file queued/rejected status |

## Safe vs Dangerous Changes

### Safe
- Adding a new supported file extension to `ingestion/validator.py`'s allow-list
- Extending `doc_metadata` (JSON column) with new optional fields

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing the `queues.parsing_queue.put()` message shape | Breaks [[Feat-0004-pipeline-workers]]'s `ParserWorker`, which reads specific keys with no schema versioning |
| Loosening `get_ingest_allowed_roles()` | Directly widens who can submit PHI-bearing documents |
| Changing the state-machine transition table | Breaks every downstream worker's `update_status()` call, which assumes the transition it's making is valid |

### Human Escalation Required
- Applying the existing `RateLimiter` ([[app/dependencies.py]]) to `POST /ingest/bulk` — it exists but is **not currently wired into this endpoint** (see Gaps); adding it changes accepted request volume for whoever calls it today.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Role not in allow-list | 403 | `HTTPException` in `app/main.py` |
| >50 files in one bulk request | 422 | explicit check |
| File fails validation (size/type/magic bytes) | per-file `"status": "rejected"` in the batch response, not an HTTP error | `_process_single_upload_bytes()` |
| Duplicate filename | per-file `"status": "rejected", "reason": "Duplicate document"` | `is_duplicate_document()` |
| S3 credentials expired/missing | `ValueError` with a remediation hint (`aws sso login ...`) | caught `TokenRetrievalError`/`NoCredentialsError` |
| S3 upload fails otherwise | `ValueError` wrapping the boto3 error | caught `ClientError`/`BotoCoreError` |
| Invalid state transition attempted | `RegistryError` | `can_transition()` returns false |

## Testing Expectations

- `tests/unit/test_bulk_ingestion.py` covers: RBAC (403 for disallowed roles), batch size limits (422 at 51 files), mixed valid/invalid batches, audit event shape (one event per batch, counts not filenames), and that one file's registration error doesn't block the others.
- Required test types going forward: one happy + one error path per new validation rule; any change to `get_ingest_allowed_roles()` needs an explicit accepted/rejected test per affected role.

## Key Files

- `app/main.py` — `POST /ingest/bulk`, `ingest_document()` Python API, per-file batch processing
- `ingestion/validator.py` — file type/size/magic-byte/DICOM validation
- `ingestion/registry.py` — document/chunk registration, duplicate detection, status updates
- `ingestion/state_machine.py` — `DocStatus` enum and valid transitions
- `ingestion/metadata/rbac_policy.py` — department→roles map, ingest-allowed-roles
- `ingestion/watcher.py` — filesystem polling ingest trigger
- `app/dependencies.py` — `RateLimiter` (token bucket, per `user_id`) — defined but not applied to the bulk endpoint

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0003-document-ingestion | touching file validation, the ingest API, the document/chunk registry, or ingest-time RBAC |

## Forbidden Patterns

- Never bypass `DocumentValidator.validate()` for a new upload path — it's the sole line of defense against executable/oversized/wrong-type files reaching S3.
- Never call `registry.update_status()` with a target state that skips a stage — `can_transition()` exists specifically to prevent that.

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| Duplicate detection is filename-based, not content-hash-based | Simpler check, but means the same content under two filenames is *not* caught (only chunk-hash dedup catches that, later, per-chunk) | Understanding this leaves a real gap for near-duplicate documents uploaded under different names |
| No auth beyond a self-asserted `role` header on the bulk endpoint | See [[Feat-0007-security-access-control]]'s repo-wide auth model note | Any change here should be coordinated with the whole-repo auth model, not patched locally |

## Known Gaps

- `RateLimiter` (`app/dependencies.py`) is defined but **not applied** to `POST /ingest/bulk` — the endpoint accepts unlimited request bursts.
- Bulk multipart files are read fully into memory before validation (`await file.read()`) — no streaming, no backpressure for large batches.
