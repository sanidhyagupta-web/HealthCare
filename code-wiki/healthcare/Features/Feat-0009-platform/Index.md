---
feat_id: Feat-0009
feature: platform
type: shared-library
domain: infra
criticality: high
touched_paths:
  - storage/s3_client.py
  - db/models.py
  - db/database.py
  - monitoring/tracing.py
depends_on: [app]
consumed_by: [app, ingestion, indexing, llm, security, workers, ui]
implements: []
tags: [s3, sqlalchemy, tracing]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| shared-library | `platform` | `storage/`, `db/`, `monitoring/` | Low-level infra with no domain logic of its own | 2026-09-17 (initial scan) |

Three small modules merged into one wiki entry because none has domain logic — they're consumed by
nearly every other feature for S3 I/O, the SQL registry, and (nominally) tracing.

## Domain Purpose

Provides the storage primitives (S3 upload/download with KMS encryption) and the persistence layer
(SQLAlchemy engine/session, the three registry tables) that the rest of the system is built on.
`monitoring/tracing.py` is included here for completeness but is dead code (see Gaps).

## Entities Owned

- [document_registry](../../Schemas/schemas.md#document_registry) *(owned by [[ingestion]]; this feature owns the engine/session that serves it)*
- [chunk_registry](../../Schemas/schemas.md#chunk_registry) *(same)*
- [audit_log](../../Schemas/schemas.md#audit_log) *(owned by [[security]]; same)*

## Invariants

- All S3 uploads request KMS encryption (or fall back to SSE-S3 if no CMK is configured) —
  `storage/s3_client.py:42-46`.
- The S3 client is a lazily-initialized module-level singleton — lost on process restart, scale-out,
  or a cold start.
- Schema is created via `Base.metadata.create_all()` at `db/database.py:init_db()` — **there is no
  migration tool anywhere in this repo** (no Alembic, no versioned SQL). See `Schemas/schemas.md`.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | S3 delete is best-effort — a `ClientError` is caught, logged as a warning, and does not propagate | `storage/s3_client.py:101-102` | LOW |
| BR-02 | `ChunkRegistry`/`AuditLog` reference other tables' primary keys with no `ForeignKey` declaration — referential integrity is application-enforced only | `db/models.py` | MEDIUM |
| BR-03 | `monitoring/tracing.py` (LangSmith config) has **zero importers anywhere in the repo** despite docstrings implying it should be wired into `run.py`/`streamlit_app.py` | absence — confirmed by the dependency-mapper's repo-wide import search | LOW |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| AWS S3 + KMS | every raw/processed file read or write across [[ingestion]] and [[workers]] | upload/download/delete via the module-level singleton client |

## Safe vs Dangerous Changes

### Safe
- Adding a new S3 helper function alongside the existing ones.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Adding real `ForeignKey` constraints to `ChunkRegistry`/`AuditLog` | Could reject inserts that currently succeed if referential data is ever inconsistent | No FK exists today; this is a behavior change, not just a schema annotation |
| Introducing a migration tool (Alembic) | Necessary for safe schema evolution eventually, but changes how `init_db()` is invoked everywhere | Every module that calls `init_db()` or relies on `create_all()` running at startup needs checking |
| Wiring up `monitoring/tracing.py` | Currently references `settings.langsmith_api_key`/`langsmith_project`, which **do not exist on `Settings`** — will raise `AttributeError` the moment it's called | Confirmed by the platform scan; `app/config.py` has no such fields today |

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| S3 credentials expired/missing | `TokenRetrievalError`/`NoCredentialsError`, surfaced by [[app]] as a `ValueError` with an SSO-login hint | `storage/s3_client.py`, caught in `app/main.py:65-69` |
| S3 delete fails | logged warning, no exception raised | `storage/s3_client.py:101-102` |
| `monitoring.tracing` called | would raise `AttributeError` on `settings.langsmith_api_key` | `app/config.py` has no such field — *this is currently avoided only because nothing calls it* |

## Testing Expectations

- No dedicated tests for `storage/`, `db/`, or `monitoring/` were found; coverage is incidental via
  tests that exercise [[ingestion]]'s registry functions against the real SQLite file.

## Forbidden Patterns

- Never call `monitoring/tracing.py`'s functions without first adding `langsmith_api_key`/`langsmith_project` to `app/config.py:Settings` — it will crash today.

## Key Files

- `storage/s3_client.py` — S3 upload/download/delete, KMS-encrypted, singleton client
- `db/models.py` — `DocumentRegistry`, `ChunkRegistry`, `AuditLog` SQLAlchemy models
- `db/database.py` — engine/session factory, `init_db()`, `get_db()` context manager
- `monitoring/tracing.py` — LangSmith tracing config; **dead code, do not assume it runs**

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0009-platform | touching S3 I/O, the SQL engine/session, or DB schema |

| Workflow | Sections to load |
|---|---|
| Adding a new persisted field | Entities Owned → the owning feature's own Index.md → Schemas/schemas.md |
| Investigating an S3 credentials error | Known Error Scenarios |
