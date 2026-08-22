# Schemas

Canonical, whole-codebase entity catalog. There is **no migration tool** in this repo (no
Alembic/Flyway) — the schema is defined once in `db/models.py` (SQLAlchemy ORM) and created at
process startup via `Base.metadata.create_all()` in `db/database.py`. Where this document says
"introduced by", it means "defined in `db/models.py`, no migration history exists."

## `document_registry`

Owner: [[Feat-0003-document-ingestion]]

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `doc_id` | String | not null | — | Primary key, a `uuid4()` string |
| `original_filename` | String | not null | — | |
| `raw_path` | String | not null | — | `s3://{bucket}/raw/{doc_id}/{filename}` |
| `file_type` | String | nullable | — | `typed_pdf` \| `scanned_pdf` \| `text`; no DB-level enum, string only |
| `status` | String | not null | — | Stores a `DocStatus` enum value as a string — see state machine below |
| `retry_count` | Integer | nullable | `0` | |
| `error_message` | Text | nullable | — | |
| `uploader_id` | String | nullable | — | Free-text; no FK to a users table (there is no users table) |
| `created_at` | DateTime | nullable | `utcnow` | |
| `updated_at` | DateTime | nullable | `utcnow`, `onupdate=utcnow` | |
| `doc_metadata` | JSON | nullable | `{}` | Open schema, tolerates evolution |

**Primary key:** `doc_id`
**Unique constraints:** none
**Foreign keys:** none declared (referenced *from* `chunk_registry.doc_id`, but not declared as a
DB-level FK in either direction — an orphaned chunk row is possible)

**Document status state machine** (`ingestion/state_machine.py`, enforced in
`ingestion/registry.py::update_status()` via `can_transition()`):

| Status | Can transition to | Trigger |
|---|---|---|
| `UPLOADED` | `VALIDATED`, `FAILED` | initial state; set by intake |
| `VALIDATED` | `PARSING`, `FAILED` | [[Feat-0004-pipeline-workers]] `ParserWorker` picks it up |
| `PARSING` | `PARSED`, `FAILED` | parser completes / OCR quality check fails |
| `PARSED` | `MARKDOWN_READY`, `FAILED` | `MarkdownWorker` completes |
| `MARKDOWN_READY` | `CHUNKED`, `FAILED` | `ChunkingWorker` completes |
| `CHUNKED` | `PII_PROCESSED`, `DUPLICATE`, `FAILED` | `PiiWorker` processes, or all chunks are duplicates |
| `PII_PROCESSED` | `EXTRACTED`, `FAILED` | `ExtractionWorker` completes |
| `EXTRACTED` | `EMBEDDED`, `FAILED` | `EmbeddingWorker` completes (fans out with keyword indexing) |
| `EMBEDDED` | `INDEXED`, `FAILED` | `KeywordIndexWorker` completes |
| `FAILED` | `PARSING` | manual/automatic retry — restarts at `PARSING`, not `UPLOADED` |
| `DUPLICATE` | *(terminal)* | — |
| `INDEXED` | *(terminal)* | — |

## `chunk_registry`

Owner: [[Feat-0003-document-ingestion]]

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `chunk_id` | String | not null | — | Primary key |
| `doc_id` | String | not null | — | Logical FK → `document_registry.doc_id`, **not enforced at the DB level** |
| `chunk_hash` | String | not null | — | **Unique** — the sole dedup mechanism for re-ingested content |
| `chunk_index` | Integer | nullable | — | Not marked `NOT NULL` despite being structurally required |
| `parent_chunk_id` | String | nullable | — | Logical self-reference, not enforced |
| `section` | String | nullable | — | |
| `page_number` | Integer | nullable | `0` | |
| `is_redacted` | Integer | nullable | `0` | 0/1 flag, not a native `Boolean` column |
| `created_at` | DateTime | nullable | `utcnow` | |

**Primary key:** `chunk_id`
**Unique constraints:** `chunk_hash` — this is the authoritative "have we already embedded this
text" check ([[Feat-0004-pipeline-workers]] `ChunkingWorker`)
**Foreign keys:** none declared (see gap above)

## `audit_log`

Owner: [[Feat-0007-security-access-control]] (`security/audit_logger.py` is the sole writer;
called from every other feature)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | Integer | not null | autoincrement | Primary key |
| `event_type` | String | not null | — | e.g. `DOCUMENT_INGESTED`, `BULK_INGEST_SUBMITTED`, `SEARCH`, `RATE_LIMITED`, `GUARDRAIL_BLOCKED`, `PII_PROCESSED` |
| `user_id` | String | nullable | — | Free-text, unvalidated — see [[Feat-0007-security-access-control]] open question on identity |
| `doc_id` | String | nullable | — | Logical FK → `document_registry.doc_id`, not enforced |
| `query` | Text | nullable | — | |
| `details` | JSON | nullable | — | Open schema, varies per `event_type` |
| `timestamp` | DateTime | nullable | `utcnow` | |

**Primary key:** `id`
**Unique constraints:** none
**Foreign keys:** none declared

## Implicit schema — vector/keyword index chunk metadata

Not a database table — this is the metadata dict attached to every chunk written into the Chroma
vector store and the in-memory BM25 index by [[Feat-0002-document-indexing]], on data produced by
[[Feat-0003-document-ingestion]]'s `ingestion/metadata/metadata_builder.py`. It is the de facto
contract that [[Feat-0005-semantic-search-qa]]'s RBAC filtering depends on — a wrong or missing
field here is invisible to Python's type system and only surfaces as a silent over- or
under-disclosure of records at query time.

Defined by `indexing/index_schema.py` (`REQUIRED_METADATA_FIELDS`) and
`ingestion/metadata/rbac_policy.py` (the `allowed_roles` values). **`validate_metadata()` in
`index_schema.py` exists but is never called** — nothing currently enforces this contract at write
time.

| Field | Type | Source |
|---|---|---|
| `patient_id` | string | caller-supplied at ingest |
| `doc_id` | string | → `document_registry.doc_id` |
| `chunk_id` | string | → `chunk_registry.chunk_id` |
| `source_file` | string | original filename |
| `source_page` | int | |
| `source_section` | string | |
| `chunk_index` | int | → `chunk_registry.chunk_index` |
| `parent_chunk_id` | string, optional | → `chunk_registry.parent_chunk_id` |
| `department` | string | one of `general`, `cardiology`, `billing`, `radiology`, `oncology` (`ingestion/metadata/rbac_policy.py`) |
| `allowed_roles` | list[string] | derived from `department` via the department→roles map — this list is what [[Feat-0007-security-access-control]]'s `filter_results_by_role()` checks the caller's role against |

Chroma additionally requires all metadata values to be `str`/`int`/`float`/`bool` — `list`
values (like `allowed_roles`) are flattened to a comma-separated string at write time
(`indexing/chroma_store.py::_sanitise_metadata()`), a lossy transform worth knowing about before
changing how `allowed_roles` is consumed downstream.

## Cross-feature foreign keys

None enforced at the database level. The two logical relationships that cross feature ownership
boundaries — `chunk_registry.doc_id → document_registry.doc_id` and
`audit_log.doc_id → document_registry.doc_id` — are both owned by the ingestion/registry side and
neither is declared as a real `FOREIGN KEY`, so orphaned rows are possible if a document row is
ever deleted independently (nothing in the codebase currently deletes `document_registry` rows).

## Definition drift

None found — `db/models.py` is the only schema definition in the repo (no migrations to drift
against it), and every reader (`ingestion/registry.py`, `security/audit_logger.py`, `app/main.py`)
uses the ORM models directly rather than a duplicated shape.

## Gaps

- No `FOREIGN KEY` constraints anywhere — referential integrity for `doc_id` and `user_id`
  columns is entirely application-level and unenforced by SQLite.
- `chunk_registry.chunk_index` is nullable despite being structurally required by every consumer.
- `chunk_registry.is_redacted` is an `Integer` 0/1 flag rather than a native boolean column.
- `indexing/index_schema.py::validate_metadata()` is dead code — the metadata contract it checks
  is never actually enforced before a chunk is written to the vector/keyword index.
