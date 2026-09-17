# Schemas

Canonical, whole-codebase entity catalog. **There is no migration tool in this repo** — no
`alembic/`, `migrations/`, or versioned SQL anywhere. The SQLAlchemy declarative models in
`db/models.py` are created directly via `Base.metadata.create_all()` (`db/database.py:init_db()`)
and are themselves the source of truth; "the migration is truth" does not apply here because there
is no migration layer to disagree with the ORM. No definition drift was found between `db/models.py`
and any other schema definition.

Three of the stores below are not SQL tables — Chroma, the BM25 index, and the PII entity index are
JSON/vector stores, included here because they are still persisted, versioned-by-nothing state that
a change to `indexing/index_schema.py` or `ingestion/metadata/rbac_policy.py` can silently break.

## document_registry

Owner: **Feat-0003-ingestion**

| Column | Type | Null | Default |
|---|---|---|---|
| `doc_id` | String | not null | — |
| `original_filename` | String | not null | — |
| `raw_path` | String | not null | — |
| `file_type` | String | null | — (`typed_pdf` \| `scanned_pdf` \| `text` \| `dicom`) |
| `status` | String | not null | — (`DocStatus` enum, see Feat-0003) |
| `retry_count` | Integer | null | `0` |
| `error_message` | Text | null | — |
| `uploader_id` | String | null | — |
| `created_at` | DateTime | null | `datetime.utcnow` |
| `updated_at` | DateTime | null | `datetime.utcnow`, on-update |
| `doc_metadata` | JSON | null | `dict` |

- **Primary key**: `doc_id`
- **No explicit `UNIQUE` constraint on `original_filename`**, despite duplicate-detection logic
  (`ingestion/registry.py:70-82`) relying on filename matching — referential/uniqueness integrity for
  duplicate detection is enforced only in application code, not the database.

Source: `db/models.py:9-22`

## chunk_registry

Owner: **Feat-0003-ingestion**

| Column | Type | Null | Default |
|---|---|---|---|
| `chunk_id` | String | not null | — |
| `doc_id` | String | not null | — |
| `chunk_hash` | String | not null | — |
| `chunk_index` | Integer | null | — |
| `parent_chunk_id` | String | null | — |
| `section` | String | null | — |
| `page_number` | Integer | null | `0` |
| `is_redacted` | Integer | null | `0` (semantic bool, not `Boolean` type) |
| `created_at` | DateTime | null | `datetime.utcnow` |

- **Primary key**: `chunk_id`
- **Unique**: `chunk_hash` — the sole document-content deduplication mechanism
  (`ingestion/registry.py:99-114`)
- **No `ForeignKey` declaration** on `doc_id` or `parent_chunk_id` despite both referencing rows in
  this and the `document_registry` table — referential integrity (e.g. orphaned chunks after a
  document delete) is not enforced by the database.

Source: `db/models.py:25-36`

## audit_log

Owner: **Feat-0006-security**

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | Integer | not null | autoincrement |
| `event_type` | String | not null | — |
| `user_id` | String | null | — |
| `doc_id` | String | null | — |
| `query` | Text | null | — |
| `details` | JSON | null | — |
| `timestamp` | DateTime | null | `datetime.utcnow` |

- **Primary key**: `id` (autoincrement)
- **No `ForeignKey`** from `doc_id` to `document_registry.doc_id` — append-only audit trail, no
  referential integrity enforced.
- Written to on a best-effort basis: `security/audit_logger.py` writes to this table **and** a local
  JSON-lines file; a DB write failure is logged and swallowed, not raised (file write still
  succeeds).

Source: `db/models.py:39-49`

## chroma_vector_store (not SQL — Chroma persistent collection)

Owner: **Feat-0002-indexing**

Collection name: `healthcare_docs` (configurable via `Settings.chroma_collection_name`). Similarity:
cosine (`hnsw:space`). Indexed by `chunk_id`.

| Metadata field | Type | Notes |
|---|---|---|
| `patient_id` | string | |
| `doc_id` | string | → `document_registry.doc_id` |
| `chunk_id` | string | → `chunk_registry.chunk_id` |
| `source_file`, `source_page`, `source_section`, `chunk_index` | string/int | provenance |
| `department` | string | enum from `ingestion/metadata/rbac_policy.py:_DEPARTMENT_ROLES` |
| `allowed_roles` | **comma-delimited string**, not a list | Chroma requires scalar metadata values; lists are joined with `,` at write time (`indexing/chroma_store.py:76-87`) |

`allowed_roles` stored as a joined string is a known footgun called out explicitly in
`AiHarness/skills/access-control.md`'s "Bad examples": storing it as a string instead of `list[str]`
risks substring-membership bugs (e.g. `"doctor" in "doc,nurse"`). Confirm the read-side check does a
real list-membership test, not a substring match, before changing this format.

`indexing/index_schema.py` defines `validate_metadata()` for this required-field set but it is
**never called** before `upsert_chunks()` — nothing currently guarantees a chunk written to Chroma
actually has all required metadata fields.

## bm25_keyword_index (not SQL — JSON-persisted)

Owner: **Feat-0002-indexing**

File: `data/bm25_index.json`. Corpus: list of `{chunk_id, text, metadata}`, same metadata shape as
Chroma above. Rebuilt from JSON on module import; rewritten to disk after every upsert
(`indexing/opensearch_index.py:50-56`). No thread lock around the in-memory corpus/BM25 objects
(unlike `pii_entity_index`, which does use one) — concurrent-write safety is unconfirmed.

## pii_entity_index (not SQL — hash-based, JSON-persisted)

Owner: **Feat-0002-indexing**

Files: `data/pii_entity_index.json` (`{sha256(entity_type:entity_value): [chunk_id, ...]}`),
`data/pii_doc_index.json` (`{doc_chunks: {doc_id: [chunk_id,...]}, chunk_doc: {chunk_id: doc_id}}`).
Stores **hashes only, never plaintext PHI** — entity values are SHA-256'd before indexing
(`indexing/pii_entity_index.py:18`). A `PERSON`/`PATIENT_NAME` hash match expands the result to every
chunk of the matched document; other entity types (MRN, DATE, PHONE, SSN, ADDRESS) return only the
specific matching chunks.

## Cross-Feature Foreign Keys

None are database-enforced (see the "no `ForeignKey`" notes above), but these are the application-level
relationships that cross feature ownership:

| Reference | Owners | Enforced by |
|---|---|---|
| `chunk_registry.doc_id` → `document_registry.doc_id` | ingestion → ingestion | application code only |
| `audit_log.doc_id` → `document_registry.doc_id` | security → ingestion | application code only |
| `chroma_vector_store.metadata.doc_id` → `document_registry.doc_id` | indexing → ingestion | application code only |
| `chroma_vector_store.metadata.chunk_id` / `bm25_keyword_index` chunk_id / `pii_entity_index` chunk_doc → `chunk_registry.chunk_id` | indexing → ingestion | application code only |
| `chroma_vector_store.metadata.allowed_roles` value set | indexing (written) ← ingestion (`rbac_policy.py`, source of truth) | `ingestion/metadata/rbac_policy.py` is the single place this value set may be edited |

## Definition Drift

None found — no ORM/DTO layer disagrees with `db/models.py`, because there is no second schema
definition for the SQL tables. `indexing/index_schema.py`'s `REQUIRED_METADATA_FIELDS` matches what
`workers/pii_worker.py` actually writes, but is unenforced (see `validate_metadata()` above).

## Gaps

- *Open question: should `document_registry.original_filename` carry a `UNIQUE` constraint, given
  duplicate detection depends on filename matching but is only enforced in application code
  (`ingestion/registry.py:70-82`)?*
- *Open question: should `chunk_registry.doc_id`/`parent_chunk_id` and `audit_log.doc_id` have real
  `ForeignKey` declarations, or is the lack of DB-level referential integrity intentional for this
  stage of the project?*
- *Open question: is `chunk_registry.is_redacted` intentionally `Integer` rather than `Boolean`, or
  is that incidental?*
- *Open question: should `indexing/index_schema.py:validate_metadata()` be wired into
  `upsert_chunks()`, or is metadata correctness meant to be guaranteed upstream by the ingestion
  pipeline instead?*
