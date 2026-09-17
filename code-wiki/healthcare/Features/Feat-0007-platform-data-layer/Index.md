---
feat_id: Feat-0007
feature: platform-data-layer
type: shared-library
domain: platform
criticality: high
touched_paths:
  - db/
  - monitoring/
depends_on: []
consumed_by: [Feat-0001, Feat-0002, Feat-0004, Feat-0006]
implements: []
tags: [database, sqlalchemy, observability]
---

## Overview

| Field | Value |
|---|---|
| Type | shared-library |
| Package | `db/`, `monitoring/` |
| Path | `db/*.py`, `monitoring/*.py` |
| Domain | platform |
| Last updated | 2026-09-17 |

## Domain Purpose

The single persistence layer (SQLite via SQLAlchemy) every other feature reads and writes
through — no feature talks to the database directly except through `db.database.get_db()` and
the three ORM models defined here. `monitoring/` is a second, much smaller shared concern
(tracing) bundled into this target because it's too small to warrant its own scan and shares
the "used by everything, owned by nothing" shape.

## Entities Owned

| Entity | Represents |
|---|---|
| [document_registry](../../Schemas/schemas.md#document_registry) | owned in practice by Feat-0002, but the table definition itself lives in this feature's `db/models.py` |
| [chunk_registry](../../Schemas/schemas.md#chunk_registry) | same — defined here, used by Feat-0001/Feat-0002 |
| [audit_log](../../Schemas/schemas.md#audit_log) | same — defined here, used by Feat-0004 |

See `Schemas/schemas.md` for full column detail — this feature is the schema's *definition*
site, not its business owner.

## Invariants

- `Base.metadata.create_all()` (via `init_db()`) is the only schema-creation mechanism — there
  is no migration history; a schema change is only as versioned as `db/models.py`'s own git
  history.
- Every write goes through `get_db()`'s context manager, which commits on clean exit and rolls
  back on any exception — no caller is expected to manage transactions itself.
- No foreign key in this schema is enforced at the database level — `chunk_registry.doc_id`,
  `chunk_registry.parent_chunk_id`, and `audit_log.doc_id` are all implicit references
  maintained entirely by application code (see `Schemas/schemas.md`'s Cross-Feature Foreign
  Keys section).

## Access Control

**Model**: none — this is a shared library, not a caller-facing surface. Access control is
enforced by the features that call into it (Feat-0002, Feat-0004), not here.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | `chunk_hash` is globally unique across all documents | `db/models.py` (`ChunkRegistry.chunk_hash`, `unique=True`) | CRITICAL |
| BR-02 | Session commits are atomic; an exception mid-block rolls back the whole transaction | `db/database.py:get_db()` | HIGH |

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| `get_db()` used before `init_db()` has run | SQLAlchemy error on first query (tables don't exist) | No explicit guard in `db/database.py` |
| Any exception inside a `with get_db()` block | Automatic rollback, exception re-raised to caller | `db/database.py:25-26` |

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| SQLite with `check_same_thread=False` | Simplicity for a single-process, multi-thread-worker deployment | Confirming a concurrent multi-process deployment isn't planned — SQLite's write concurrency will become a bottleneck first |

## Forbidden Patterns

- Never write to `document_registry`/`chunk_registry`/`audit_log` outside `get_db()`'s session — every write must go through the shared commit/rollback path.
- Never assume a foreign key here is enforced by the database — `doc_id`/`parent_chunk_id` references are application-maintained only (see Invariants).

## Key Files

- `db/database.py` — engine/session factory, `init_db()`, `get_db()` context manager
- `db/models.py` — `Base`, `DocumentRegistry`, `ChunkRegistry`, `AuditLog`
- `monitoring/tracing.py` — LangSmith tracing facade (`configure_tracing()`, `is_active()`) — **defined but never called anywhere in the codebase**; `app/config.py` doesn't even define the `settings.langsmith_api_key`/`settings.langsmith_project` fields this module reads, so calling it today would raise `AttributeError`. Treat as dead/unfinished, not as live observability.

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0002 (Document Ingestion Pipeline) | changing `document_registry`/`chunk_registry` columns or constraints |
| Feat-0004 (Security & Access Control) | changing `audit_log` columns |

| Workflow | Sections to load |
|---|---|
| Add a column to an existing table | Entities Owned, Invariants, `Schemas/schemas.md` |
| Wire up `monitoring/tracing.py` for real | Key Files (the `AttributeError` gap must be fixed in `app/config.py` first) |
