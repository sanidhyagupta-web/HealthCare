---
feat_id: Feat-0008
feature: storage-persistence
type: shared-library
domain: persistence
criticality: high
touched_paths:
  - storage/s3_client.py
  - db/models.py
  - db/database.py
depends_on: []
consumed_by: [Feat-0003-document-ingestion, Feat-0004-pipeline-workers, Feat-0006-streamlit-ui, Feat-0007-security-access-control]
implements: []
tags: [persistence, s3, sqlite, sqlalchemy]
---

## Overview

| | |
|---|---|
| Type | shared-library |
| Package | `storage/` + `db/` |
| Path | `storage/s3_client.py`, `db/models.py`, `db/database.py` |
| Domain | Raw document blob storage (S3) and structured registry state (SQLite via SQLAlchemy) |
| Last updated | initial scan |

## Domain Purpose

Provides the two persistence primitives every other feature builds on: an encrypted S3 wrapper
for document bytes, and a SQLite-backed ORM session for the document/chunk/audit registry tables.

## Entities Owned

- `document_registry` → [[Schemas/schemas.md#document_registry]] (co-owned in practice with [[Feat-0003-document-ingestion]], which is the primary writer — this library only defines the table and the session machinery)
- `chunk_registry` → [[Schemas/schemas.md#chunk_registry]]
- `audit_log` → [[Schemas/schemas.md#audit_log]] (primary writer is [[Feat-0007-security-access-control]]'s `audit_logger.py`)

## Invariants

- Every S3 upload is encrypted — KMS if `KMS_KEY_ID` is set, SSE-S3 fallback otherwise; there is no plaintext upload path in `s3_client.py`.
- `get_db()`'s context manager commits on success and rolls back on any exception — callers never need to manage the transaction boundary themselves.
- **No migration tool exists** — schema changes are made directly in `db/models.py` and take effect via `Base.metadata.create_all()`, which only creates missing tables; it does not alter existing ones.

## Access Control

**Model**: none — this is a pure persistence layer with no auth primitives of its own. Every
consumer is responsible for its own authorization before calling in.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | S3 encryption mode: KMS when `kms_key_id` configured, SSE-S3 otherwise | `storage/s3_client.py` | HIGH |
| BR-02 | `chunk_registry.chunk_hash` is DB-level `UNIQUE` — the sole document-content dedup mechanism | `db/models.py` | HIGH |
| BR-03 | DB session rolls back automatically on any exception inside `get_db()`'s block | `db/database.py` | HIGH |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| AWS S3 (+ optional KMS) | every `upload`/`upload_file`/`download_bytes`/`download_to_tempfile`/`delete` call | boto3 client, module-level cached (`_s3` global) |
| SQLite (`db/healthcare_registry.db`) | every registry read/write | single-file DB, no separate DB server |

## Safe vs Dangerous Changes

### Safe
- Adding a new nullable column to an existing model (no migration needed since there's no migration tool to keep in sync — `create_all()` won't retrofit it onto an existing table, though, so this only works for a *fresh* database)

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Adding a `NOT NULL` column or a new `FOREIGN KEY` to an existing model | `Base.metadata.create_all()` does not alter existing tables — this would require a manual migration path that doesn't currently exist in this repo | 
| Changing the S3 key naming convention (`raw/{doc_id}/{filename}`, `processed/{doc_id}/...`) | Breaks every reader across [[Feat-0003-document-ingestion]] and [[Feat-0004-pipeline-workers]] that constructs or parses these paths | 
| Removing the KMS/SSE-S3 fallback logic | Could silently produce unencrypted uploads depending on config state |

### Human Escalation Required
- Introducing a real migration tool (Alembic) — needed before this schema can safely evolve past its current fixed shape in production.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| S3 upload/download failure | unhandled `ClientError`/`BotoCoreError` propagates to caller | only `delete()` catches and swallows `ClientError`; upload/download do not |
| DB session exception | rolled back, re-raised to caller | `db/database.py::get_db()` |
| Document not found on status update | `RegistryError` (raised by the calling feature, not this library) | — |

## Testing Expectations

*Open question: no dedicated tests for `storage/s3_client.py` or `db/` found in `tests/unit/` —
coverage comes indirectly through [[Feat-0003-document-ingestion]]'s `test_bulk_ingestion.py`,
which mocks S3 and the registry entirely rather than testing this library directly.*

## Key Files

- `storage/s3_client.py` — upload/download/delete wrapper, KMS/SSE-S3 encryption mode selection
- `db/models.py` — `DocumentRegistry`, `ChunkRegistry`, `AuditLog` ORM models
- `db/database.py` — engine setup, `SessionLocal`, `init_db()`, `get_db()` context manager

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0008-storage-persistence | touching S3 upload/download logic, the ORM models, or DB session handling |

## Forbidden Patterns

- Never add a new required (`NOT NULL`, no default) column to an existing model and assume `create_all()` will apply it to an already-created database — it won't; existing databases need a manual `ALTER TABLE` or a fresh DB.
- Never construct an S3 key by hand outside this library's existing `raw/{doc_id}/...` / `processed/{doc_id}/...` conventions — every reader assumes them.

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| SQLite instead of a networked database | Single-process prototype deployment simplicity | Understanding this means no concurrent-writer story beyond SQLite's own file-locking — a move to multi-process/multi-host deployment would need a real DB first |
| No migration tool (Alembic) | Prototype speed | Any schema change beyond adding a nullable column to a fresh DB needs manual coordination — this is worth fixing before the schema needs its first real change |

## Known Gaps

- No `FOREIGN KEY` constraints declared anywhere (`chunk_registry.doc_id`, `audit_log.doc_id` are logical-only references) — see [[Schemas/schemas.md]] for the full list.
- `storage/s3_client.py::download_bytes()`/`upload()`/`upload_file()` don't catch `ClientError` — only `delete()` does, and it swallows the error rather than surfacing it distinctly from a "key didn't exist" case.
- No connection pooling/lifecycle management documented for the S3 client beyond a module-level cache — relevant if this is ever deployed in a scaled-out or FaaS context.
