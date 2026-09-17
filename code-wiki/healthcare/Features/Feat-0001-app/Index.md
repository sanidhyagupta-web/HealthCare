---
feat_id: Feat-0001
feature: app
type: backend-service
domain: api-bootstrap
criticality: high
touched_paths:
  - app/main.py
  - app/config.py
  - app/dependencies.py
depends_on: [ingestion, security, platform, workers]
consumed_by: [ui, ingestion, security, indexing, llm, platform, workers]
implements: []
tags: [api, bootstrap, fastapi, config]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | `app` | `app/` | API bootstrap / cross-cutting config | 2026-09-17 (initial scan) |

## Domain Purpose

The HTTP entry point and app-wide configuration for a healthcare document ingestion + RAG system.
It exposes the one HTTP endpoint in the whole repo (`POST /ingest/bulk`) and owns `Settings`, the
single configuration object almost every other module reads.

## Invariants

- No file failure in a batch blocks the rest of the batch — each file's outcome is caught and
  reported independently (`app/main.py:108-147`).
- Exactly one `BULK_INGEST_SUBMITTED` audit event is emitted per batch, not per file
  (`app/main.py:188-192`).
- A document's DB status is always set to `VALIDATED` before it is enqueued
  (`app/main.py:74, 130`).
- S3 uploads always request KMS encryption for raw files (`app/main.py:61`).

## Access Control

**Model**: role string, self-asserted via HTTP header — see [[security]] and
`.claude/rules/security.md` for the full caveat.

| Action | Access Condition | Enforced In |
|---|---|---|
| `POST /ingest/bulk` | `role` header ∈ `get_ingest_allowed_roles()` (`doctor`, `nurse`, `admin`) | `app/main.py:168-169` |
| `ingest_document()` (Python API, used by `ui/upload_page.py`) | **none** | nowhere — no role check on this path |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Bulk ingest capped at 50 files per request | `app/main.py:171-172` | MEDIUM |
| BR-02 | Only `doctor`/`nurse`/`admin` roles may submit via the HTTP endpoint | `app/main.py:168-169` | CRITICAL |
| BR-03 | The `role`/`uploader_id`/`patient_id`/`department` headers are trusted with no verification of caller identity | `app/main.py:154-161` | CRITICAL |
| BR-04 | Duplicate filenames are rejected per-file, not batch-aborted | `app/main.py:116-117` | LOW |
| BR-05 | `rate_limiter` (`app/dependencies.py`) is defined and used by the Streamlit UI pages, but **not applied to `POST /ingest/bulk`** | — (absence) | HIGH |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| AWS S3 (via [[platform]]) | every ingest (single or bulk) | raw file uploaded with KMS encryption before any DB row is written |
| in-process queue ([[workers]]) | after successful validation + S3 upload + DB register | document enqueued onto `parsing_queue` |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|---|---|---|---|---|
| POST | `/ingest/bulk` | self-asserted `role` header, no signature/session check | not currently called by the Streamlit UI (which calls the Python API `ingest_document()`/`_process_single_upload_bytes()` directly, in-process) — reachable directly over HTTP by anyone who can set headers | Accepts up to 50 files, validates/uploads/registers/enqueues each independently |

## Safe vs Dangerous Changes

### Safe
- Adding a new file-type/MIME check inside `DocumentValidator` (delegated to [[ingestion]]).
- Raising the 50-file batch cap (update `app/main.py:171` and its accompanying test).

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Trusting the `role` header as authorization without adding real authentication | Privilege escalation | Anyone with network access to this endpoint can claim `role: admin` today — see `.claude/rules/security.md` |
| Removing the try/except in `_process_single_upload_bytes` | One bad file aborts the whole batch | Currently isolates per-file failures (`app/main.py:145-147`) |
| Calling `init_db()` conditionally or removing it from wherever it's actually invoked | Ingest silently fails with a DB error | `init_db` is imported at `app/main.py:17` but **never called in `app/main.py` itself** — some other entry point (likely `run.py`) must call it first |

### Human Escalation Required
- Any change that makes `POST /ingest/bulk` more permissive (new default role, wider file-count cap) given it currently has no real authentication.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Missing `role` header | HTTP 422 | FastAPI required-header validation |
| Role not in allow-list | HTTP 403 "Insufficient role for bulk ingest" | `app/main.py:168-169` |
| >50 files | HTTP 422 "Maximum 50 files per batch" | `app/main.py:171-172` |
| AWS creds expired/missing | `ValueError` with an `aws sso login` hint | `app/main.py:65-69` |
| S3 client/boto error | `ValueError("S3 upload failed: ...")` | `app/main.py:70-71` |
| Any other per-file exception | file marked `rejected` in the response, batch continues | `app/main.py:145-147` |

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| `app/config.py:Settings` is a single dataclass instance imported everywhere | One place for all environment-driven config | Checking every module in [[ingestion]], [[indexing]], [[llm]], [[platform]], [[security]], [[workers]] that reads `settings.*` |

## Forbidden Patterns

- Never treat the `role`/`uploader_id` headers on `/ingest/bulk` as verified identity in new code — they are not (see Business Rules BR-03).
- Never let one file's exception in a bulk batch propagate and abort the remaining files.

## Key Files

- `app/main.py` — FastAPI app, `POST /ingest/bulk`, and the `ingest_document()`/`_process_single_upload_bytes()` Python API shared with the Streamlit UI
- `app/config.py` — `Settings` dataclass; the one configuration surface for the whole repo
- `app/dependencies.py` — `RateLimiter` (in-memory, per-process, token-bucket)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0001-app | touching `/ingest/bulk`, `Settings`, or the rate limiter |

| Workflow | Sections to load |
|---|---|
| Adding a new endpoint | API Endpoints, Access Control, Business Rules |
| Changing a config default | Architectural Decisions, then grep every consumer of `settings.<field>` |
