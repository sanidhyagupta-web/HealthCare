# Schemas — HealthCare

Canonical, whole-codebase entity catalog. There are no database migrations in this repo — the
schema is defined directly in SQLAlchemy ORM model classes (`db/models.py`) and created via
`Base.metadata.create_all()` at startup (`db/database.py:init_db()`). The model class is both the
"migration" and the current-state definition; there is nothing to reconcile against, so
Definition Drift is empty by construction, not because nothing was checked.

Non-relational persisted structures (vector store, keyword index, PII hash indexes) are cataloged
here too, since they are equally part of the codebase's persisted state.

---

## document_registry

**Owner:** Feat-0001 (Document Ingestion Pipeline) — written by `ingestion/registry.py`

| Column | Type | Nullable | Default |
|---|---|---|---|
| doc_id | string | not null (PK) | — |
| original_filename | string | not null | — |
| raw_path | string | not null | — |
| file_type | string | nullable | — |
| status | string | not null | — |
| retry_count | integer | nullable | 0 |
| error_message | text | nullable | — |
| uploader_id | string | nullable | — |
| created_at | datetime | nullable | `utcnow` |
| updated_at | datetime | nullable | `utcnow` (onupdate `utcnow`) |
| doc_metadata | JSON | nullable | `{}` |

Primary key: `doc_id`. No foreign keys, no unique constraints beyond the primary key.

## chunk_registry

**Owner:** Feat-0001 (Document Ingestion Pipeline) — written by `ingestion/registry.py`

| Column | Type | Nullable | Default |
|---|---|---|---|
| chunk_id | string | not null (PK) | — |
| doc_id | string | not null | — |
| chunk_hash | string | not null (**UNIQUE**) | — |
| chunk_index | integer | nullable | — |
| parent_chunk_id | string | nullable | — |
| section | string | nullable | — |
| page_number | integer | nullable | 0 |
| is_redacted | integer (0/1 — not a real boolean) | nullable | 0 |
| created_at | datetime | nullable | `utcnow` |

Primary key: `chunk_id`. `chunk_hash` UNIQUE — this is the mechanism that prevents re-ingesting
identical chunk content twice (see Feat-0001 Business Rules).

`doc_id` semantically references `document_registry.doc_id`, but **no FK constraint is declared
in the ORM model** — referential integrity relies entirely on application logic (Gap).

## audit_log

**Owner:** Feat-0005 (Security & Access Control) — written by `security/audit_logger.py`

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | not null (PK, autoincrement) | — |
| event_type | string | not null | — |
| user_id | string | nullable | — |
| doc_id | string | nullable | — |
| query | text | nullable | — |
| details | JSON | nullable | — |
| timestamp | datetime | nullable | `utcnow` |

Primary key: `id`. `doc_id` semantically references `document_registry.doc_id` (optional, no FK
constraint declared).

Event types observed in use: `VALIDATION_FAILED`, `DOCUMENT_INGESTED`, `BULK_INGEST_SUBMITTED`,
`PII_PROCESSED`, `SEARCH`, `RATE_LIMITED`, `GUARDRAIL_BLOCKED`.

---

## chroma_collection (`healthcare_docs`)

**Owner:** Feat-0003 (Search & Retrieval) — written by `indexing/chroma_store.py`. Not relational —
a ChromaDB vector collection.

| Field | Type | Notes |
|---|---|---|
| chunk_id | string | primary identifier |
| embedding | list[float] | sentence-transformers embedding |
| text | string | redacted chunk text ([ENTITY_TYPE] placeholders) |
| metadata | dict | required fields enforced by `indexing/index_schema.py`: `patient_id`, `doc_id`, `chunk_id`, `source_file`, `source_page`, `source_section`, `chunk_index`, `department`, `allowed_roles` |

No database-level schema validation — required-field checking happens only at the application
layer (`index_schema.validate_metadata`). `chunk_id` → `chunk_registry.chunk_id` and
`metadata.doc_id` → `document_registry.doc_id` are both semantic-only references.

## bm25_index (`data/bm25_index.json`)

**Owner:** Feat-0003 (Search & Retrieval) — written by `indexing/opensearch_index.py`. Persisted
JSON file backing an in-memory BM25 (`rank-bm25`) keyword index.

| Field | Type | Notes |
|---|---|---|
| chunk_id | string | primary identifier |
| text | string | indexed chunk text |
| metadata | dict | same shape as the Chroma entry |

`chunk_id` → `chunk_registry.chunk_id` (semantic only).

## pii_entity_index (`data/pii_entity_index.json`)

**Owner:** Feat-0005 (Security & Access Control) — written by `indexing/pii_entity_index.py`
during `PiiWorker` processing.

| Field | Type | Notes |
|---|---|---|
| entity_hash | string (PK) | SHA-256 of `entity_type:entity_value` — raw PII is never stored |
| chunk_ids | list[string] | chunks containing that entity |

Used at query time to pre-filter retrieval to chunks matching a detected PII entity in the user's
query (patient-name/MRN-scoped search).

## pii_doc_index (`data/pii_doc_index.json`)

**Owner:** Feat-0005 (Security & Access Control) — written alongside `pii_entity_index`.

| Field | Type | Notes |
|---|---|---|
| doc_chunks | dict[doc_id → list[chunk_id]] | forward index |
| chunk_doc | dict[chunk_id → doc_id] | reverse index |

Used to expand a `PERSON`/`PATIENT_NAME` entity match to every chunk in the same document, not
just the matching chunk (see Feat-0003 Business Rules).

---

## Cross-Feature Foreign Keys

All of the following are **semantic references only** — none are enforced by an actual FK
constraint at the storage layer (SQLite ORM or vector/JSON store). This is a Gap common to every
entity in this schema, not repeated per row below.

| From | To | Owners |
|---|---|---|
| `chunk_registry.doc_id` | `document_registry.doc_id` | Feat-0001 → Feat-0001 (same feature) |
| `audit_log.doc_id` | `document_registry.doc_id` | Feat-0005 → Feat-0001 |
| `chroma_collection.metadata.doc_id` | `document_registry.doc_id` | Feat-0003 → Feat-0001 |
| `chroma_collection.chunk_id` | `chunk_registry.chunk_id` | Feat-0003 → Feat-0001 |
| `bm25_index.chunk_id` | `chunk_registry.chunk_id` | Feat-0003 → Feat-0001 |
| `pii_entity_index.chunk_ids[]` | `chunk_registry.chunk_id` | Feat-0005 → Feat-0001 |
| `pii_doc_index.chunk_ids[]` / `doc_chunks[]` | `chunk_registry.chunk_id` / `document_registry.doc_id` | Feat-0005 → Feat-0001 |

## Definition Drift

None found — there is no migrations layer to disagree with; `db/models.py` is the only and
authoritative schema source.

## Gaps

- No FK constraints declared anywhere in `db/models.py` despite several semantic references
  (`chunk_registry.doc_id`, `audit_log.doc_id`) — referential integrity is application-enforced
  only.
- `chunk_registry.is_redacted` is an integer (0/1), not a real boolean column.
- Vector/keyword/PII-index "schemas" (Chroma metadata, BM25 JSON, PII hash indexes) are enforced
  only at the application layer (`indexing/index_schema.py`), with no storage-level validation —
  a caller that skips `validate_metadata` can write a record missing `allowed_roles`, silently
  breaking RBAC filtering for that chunk.
