---
feat_id: Feat-0003
feature: ingestion
type: backend-service
domain: document-intake
criticality: high
touched_paths:
  - ingestion/validator.py
  - ingestion/registry.py
  - ingestion/state_machine.py
  - ingestion/watcher.py
  - ingestion/pii/
  - ingestion/parsers/
  - ingestion/markdown/
  - ingestion/ocr/
  - ingestion/chunking/
  - ingestion/metadata/
depends_on: [platform, app]
consumed_by: [ui, app, workers, search]
implements: []
tags: [rbac, pii, state-machine, document-parsing]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | `ingestion` | `ingestion/` | Document intake, validation, parsing, PII, RBAC policy | 2026-09-17 (initial scan) |

## Domain Purpose

Validates and tracks every uploaded healthcare document through a strict lifecycle, from raw upload
to PII-redacted, chunked, role-tagged content ready to index. Owns the single source of truth for
which roles may access which department's documents.

## Entities Owned

- [document_registry](../../Schemas/schemas.md#document_registry) — one row per uploaded document
- [chunk_registry](../../Schemas/schemas.md#chunk_registry) — one row per deduplicated content chunk

## Status / State Machine

| Status | Business Meaning | Can Transition To | Trigger |
|---|---|---|---|
| `UPLOADED` | initial state on registration | `VALIDATED`, `FAILED` | file validated |
| `VALIDATED` | passed extension/size/magic-byte checks | `PARSING`, `FAILED` | worker picks up |
| `PARSING` → `PARSED` | text extraction (incl. OCR) | `MARKDOWN_READY`, `FAILED` | [[workers]] `ParserWorker` |
| `MARKDOWN_READY` | converted to structured markdown | `CHUNKED`, `FAILED` | `MarkdownWorker` |
| `CHUNKED` | entity-preserving chunking + dedup done | `PII_PROCESSED`, `DUPLICATE`, `FAILED` | `ChunkingWorker` |
| `DUPLICATE` (terminal) | every chunk hash already existed | — | all chunks were dupes |
| `PII_PROCESSED` | PII detected, redacted, encrypted, RBAC-tagged | `EXTRACTED`, `FAILED` | `PiiWorker` |
| `EXTRACTED` → `EMBEDDED` → `INDEXED` (terminal) | drug/ADE extraction, embedding, indexing | `FAILED` at each step | [[workers]], [[indexing]] |
| `FAILED` | any stage errored | `PARSING` (retry) | `can_transition()` guard |

Transition constraint: **every transition is validated by `can_transition()`**
(`ingestion/state_machine.py:36-37`); an invalid transition raises `RegistryError`
(`ingestion/registry.py:48-51`) rather than silently updating status.

## Invariants

- Plaintext PII never persists to local disk — text stays in S3 or in-memory queue messages until
  redacted (`ingestion/pii/pii_redactor.py`).
- `chunk_hash` (SHA-256 of normalized text) is the sole dedup key; if every chunk of a re-uploaded
  document hash-matches existing chunks, the document is marked `DUPLICATE` and processing stops.
- State transitions are one-directional except `FAILED → PARSING` (retry).
- Any multi-line medical concept (medication + dosage + timing) is grouped atomically and never
  split across chunks (`ingestion/chunking/entity_preserving_chunker.py:108-169`).

## Access Control

**Model**: role-based, department-scoped. `ingestion/metadata/rbac_policy.py` is the **single
source of truth** — "never hardcode a role list anywhere else" is enforced by convention, not code.

| Action | Access Condition | Enforced In |
|---|---|---|
| Submit a document (bulk HTTP) | `role` ∈ `{doctor, nurse, admin}` | `ingestion/metadata/rbac_policy.py:38-40`, checked at `app/main.py:168` |
| Submit a document (single-file Python API) | **no check** | `app/main.py:37` `ingest_document()` — gap, see Known Error Scenarios |
| Read a chunk at query time | caller's role ∈ chunk's `allowed_roles` (derived from department) | [[security]] `filter_results_by_role`, populated here at ingest time |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Department must be a known key in `_DEPARTMENT_ROLES`; unknown departments fail loudly | `ingestion/metadata/rbac_policy.py:27-31` | CRITICAL |
| BR-02 | File extension restricted to `.pdf`/`.txt`/`.text`/`.dcm`; size capped at 50MB; executable magic bytes (PE/ELF/shebang) rejected | `ingestion/validator.py:10,44-57` | CRITICAL |
| BR-03 | DICOM files must have a valid 128-byte-offset `DICM` preamble | `ingestion/validator.py:59-63` | HIGH |
| BR-04 | OCR output below `ocr_confidence_threshold` (default 0.40) fails the document | `ingestion/ocr/ocr_quality.py:26-33` | HIGH |
| BR-05 | Duplicate-by-filename check runs on the **bulk** upload path but not the **single-file** `ingest_document()` path | `app/main.py:37-90` (absence) | MEDIUM |
| BR-06 | Query-time role masking differs by role: researcher masks `PATIENT_NAME`/`MRN`/`DATE`/`PHONE`/`EMAIL`/`SSN`/demographics; admin/billing also mask clinical fields; doctor/nurse/cardiologist see full redacted text | `ingestion/pii/role_based_masking.py:25-75` | CRITICAL |
| BR-07 | Retry count capped (default 3); exceeded retries route to DLQ | `workers/base_worker.py:32-36` (uses this feature's registry) | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| Presidio (optional) | PII detection | falls back to regex patterns if unavailable (`ingestion/pii/pii_detector.py:100-106`) |
| Sapling medical spellcheck API (optional) | OCR quality pass | falls back to regex corrections on failure |
| Filesystem watcher (`ingestion/watcher.py`) | polls `raw/{pdfs,scanned,text}/` every ~5s | auto-ingests found files with `uploader_id="watcher"`, **no auth** |

## API Endpoints

None directly — consumed via `app/main.py`'s `POST /ingest/bulk` and Python API (see [[app]]).

## Safe vs Dangerous Changes

### Safe
- Adding a new department to `_DEPARTMENT_ROLES`.
- Adding a new file extension to the validator's allow-list.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Adding a role list anywhere outside `rbac_policy.py` | Access-control drift | Documented failure mode in `AiHarness/skills/access-control.md` |
| Changing PII detection/masking rules | Previously-ingested chunks keep old redaction; new rules only apply going forward | No re-scan-on-rule-change mechanism exists |
| Removing the `can_transition()` guard or loosening `VALID_TRANSITIONS` | Out-of-order processing (e.g. skipping PII redaction) | This is the sole enforcement point for pipeline ordering |

### Human Escalation Required
- Any change to `_DEPARTMENT_ROLES` or `_INGEST_ALLOWED_ROLES` that widens who can read or submit PHI.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Validation failure | file copied to `failed/validation/`, `ValueError`, `VALIDATION_FAILED` audit event | `app/main.py:51-56` |
| Unknown department at PII stage | `ValueError` | `ingestion/metadata/rbac_policy.py:27-31` |
| Invalid state transition | `RegistryError` | `ingestion/registry.py:49-51` |
| OCR below quality threshold | document → `FAILED`, sent to DLQ | `workers/parser_worker.py:65-67,75-78` |
| Single-file ingest bypasses duplicate check | duplicate content ingested twice if bulk and single-file paths both used | `app/main.py:37-90` has no `is_duplicate_document()` call |

## Testing Expectations

- `tests/unit/test_researcher_role.py` covers PII masking + RBAC filtering for the `researcher` role end-to-end.
- `tests/unit/test_bulk_ingestion.py`, `tests/unit/test_dicom_parser.py` cover bulk-ingest and DICOM validation paths.
- *Open question: is there test coverage for the state-machine guard (`can_transition`) itself, independent of a full pipeline run?*

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| RBAC role lists live in exactly one file (`rbac_policy.py`) | Prevent drift between ingest-time tagging and query-time enforcement | Grepping for any hardcoded role list before merging |

## Forbidden Patterns

- Never hardcode a role list outside `ingestion/metadata/rbac_policy.py`.
- Never let a state transition happen without going through `can_transition()`.
- Never write plaintext PII to local disk.

## Key Files

- `ingestion/state_machine.py` — `DocStatus` enum + `VALID_TRANSITIONS` + `can_transition()`
- `ingestion/registry.py` — document/chunk registration and status updates
- `ingestion/validator.py` — file validation (extension, size, magic bytes, DICOM preamble)
- `ingestion/metadata/rbac_policy.py` — department→roles map, ingest-allowed roles (single source of truth)
- `ingestion/pii/pii_detector.py`, `pii_redactor.py`, `role_based_masking.py` — PII detect/redact/mask
- `ingestion/chunking/entity_preserving_chunker.py` — medical-entity-aware chunk splitting
- `ingestion/watcher.py` — unauthenticated filesystem auto-ingest

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0003-ingestion | touching validation, the state machine, PII rules, or RBAC role/department mapping |

| Workflow | Sections to load |
|---|---|
| Adding a new role or department | Access Control, Business Rules BR-01/BR-06, Forbidden Patterns |
| Debugging a stuck document | Status/State Machine, Known Error Scenarios |
