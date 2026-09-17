# Schemas — HealthCare

Canonical, whole-codebase entity catalog. There is no migration framework in this repo —
schema is defined once, in `db/models.py`, as SQLAlchemy declarative models, and applied via
`Base.metadata.create_all()` at `db/database.py:init_db()`. Everywhere this file would normally
cite a migration, it instead says **"no migration — SQLAlchemy declarative model, `db/models.py`"**.

Two other entity shapes are cataloged here too, because they are shared across features the
same way a SQL table would be: the search-index chunk schema (Chroma + BM25), and two on-disk
JSON indexes used for PII lookups. Neither is a SQL table, but both are persisted, cross-feature
data structures — the same reason this file exists at all.

---

## document_registry

owner: [Feat-0002 (Document Ingestion Pipeline)](../Features/Feat-0002-document-ingestion-pipeline/Index.md)

| Column | Type | Null | Default |
|---|---|---|---|
| doc_id | String | not null | — (PK) |
| original_filename | String | not null | — |
| raw_path | String | not null | — (S3 key, `s3://bucket/raw/{doc_id}/{filename}`) |
| file_type | String | null | — (`typed_pdf` \| `scanned_pdf` \| `text` \| dicom) |
| status | String | not null | — (`DocStatus` enum value) |
| retry_count | Integer | null | 0 |
| error_message | Text | null | — |
| uploader_id | String | null | — |
| created_at | DateTime | null | `utcnow` |
| updated_at | DateTime | null | `utcnow` |
| doc_metadata | JSON | null | `{}` |

**Primary key:** doc_id
**Constraints:** none beyond PK (no unique/check constraints, no enforced FK)
**Introduced:** no migration — SQLAlchemy declarative model, `db/models.py`

---

## chunk_registry

owner: [Feat-0002 (Document Ingestion Pipeline)](../Features/Feat-0002-document-ingestion-pipeline/Index.md)

| Column | Type | Null | Default |
|---|---|---|---|
| chunk_id | String | not null | — (PK) |
| doc_id | String | not null | — (references document_registry.doc_id — **not** an enforced FK) |
| chunk_hash | String | not null | — (SHA256, **UNIQUE**) |
| chunk_index | Integer | null | — |
| parent_chunk_id | String | null | — (self-referential, **not** an enforced FK) |
| section | String | null | — |
| page_number | Integer | null | 0 |
| is_redacted | Integer | null | 0 |
| created_at | DateTime | null | `utcnow` |

**Primary key:** chunk_id
**Unique:** chunk_hash — the sole enforcement point for cross-document chunk deduplication
**Foreign keys:** doc_id → document_registry.doc_id (implicit — no DB-level constraint); parent_chunk_id → chunk_registry.chunk_id (implicit, self-referential)
**Introduced:** no migration — SQLAlchemy declarative model, `db/models.py`

*Open question: since neither doc_id nor parent_chunk_id is an enforced foreign key, a document
delete (if one is ever implemented) would orphan its chunks silently — is a cascade-delete or a
cleanup job planned?*

---

## audit_log

owner: [Feat-0004 (Security & Access Control)](../Features/Feat-0004-security-access-control/Index.md)

| Column | Type | Null | Default |
|---|---|---|---|
| id | Integer | not null | — (PK, autoincrement) |
| event_type | String | not null | — |
| user_id | String | null | — |
| doc_id | String | null | — (references document_registry.doc_id — **not** an enforced FK) |
| query | Text | null | — |
| details | JSON | null | — |
| timestamp | DateTime | null | `utcnow` |

**Primary key:** id
**Constraints:** none — append-only by convention, not by DB enforcement
**Introduced:** no migration — SQLAlchemy declarative model, `db/models.py`

---

## chunk_metadata (search-index document schema — not a SQL table)

owner: [Feat-0005 (Semantic Search & Indexing)](../Features/Feat-0005-semantic-search-indexing/Index.md)

The metadata dict attached to every entry in the Chroma vector-store collection
(`healthcare_docs`) and the in-memory BM25 keyword index (`indexing/opensearch_index.py`).
Validated against `indexing/index_schema.py`'s `REQUIRED_METADATA_FIELDS` — there is no DB
schema behind it, so this is the closest thing to one.

| Field | Type | Notes |
|---|---|---|
| patient_id | string | PII identifier |
| doc_id | string | → document_registry.doc_id |
| chunk_id | string | → chunk_registry.chunk_id |
| source_file | string | original filename |
| source_page | integer | page number |
| source_section | string | section heading/label |
| chunk_index | integer | position within document |
| parent_chunk_id | string, optional | parent chunk if a sub-chunk |
| department | string | one of `general`, `cardiology`, `billing`, `radiology`, `oncology` |
| allowed_roles | list[string] | written at ingest from `ingestion/metadata/rbac_policy.py:get_allowed_roles(department)`; the sole basis for query-time RBAC filtering |
| extracted_drugs | string | comma-separated, from the LLM Extraction feature |
| extracted_ades | string | comma-separated adverse-drug-events, from the LLM Extraction feature |

*Open question: `entity_types` (the list of detected PII entity types per chunk) is produced
during chunking and read by `ingestion/pii/role_based_masking.py:apply_role_mask()`, but is not
actually written into this metadata dict by `pii_worker` before it's indexed into Chroma/BM25 —
confirmed by both the Search & Indexing scan and this schema pass. `apply_role_mask()` will see
an empty/missing `entity_types` at query time. Is this a real gap (role masking silently doing
less than intended), or is `entity_types` reconstructed some other way at query time?*

---

## pii_entity_index (on-disk JSON — not a SQL table)

owner: [Feat-0005 (Semantic Search & Indexing)](../Features/Feat-0005-semantic-search-indexing/Index.md)

File: `data/pii_entity_index.json`. Maps `SHA256(entity_type:entity_value)` → list of
`chunk_id`s containing that entity. Plaintext PII values are never stored — only hashes.
Thread-safe via a `threading.Lock` in `indexing/pii_entity_index.py`.

| Key | Value |
|---|---|
| sha256_hash (string) | chunk_ids (list[string]) → chunk_registry.chunk_id |

**Introduced:** no migration — file created/maintained by `indexing/pii_entity_index.py`

---

## pii_document_chunk_index (on-disk JSON — not a SQL table)

owner: [Feat-0005 (Semantic Search & Indexing)](../Features/Feat-0005-semantic-search-indexing/Index.md)

File: `data/pii_doc_index.json`. Bidirectional doc↔chunk map used to expand a `PATIENT_NAME`/
`PERSON` entity hit to every chunk of the same document at query time (Top-D pre-filtering).

| Key | Value |
|---|---|
| doc_chunks (doc_id → list[chunk_id]) | → document_registry.doc_id, chunk_registry.chunk_id |
| chunk_doc (chunk_id → doc_id) | → chunk_registry.chunk_id, document_registry.doc_id |

**Introduced:** no migration — file created/maintained by `indexing/pii_entity_index.py`

---

## Cross-Feature Foreign Keys

| Reference | Owners |
|---|---|
| audit_log.doc_id → document_registry.doc_id | Security & Access Control → Document Ingestion Pipeline |
| chunk_metadata (Chroma/BM25) → chunk_registry.chunk_id, document_registry.doc_id | Semantic Search & Indexing → Document Ingestion Pipeline |
| pii_entity_index chunk_ids → chunk_registry.chunk_id | Semantic Search & Indexing → Document Ingestion Pipeline |
| pii_document_chunk_index doc_id/chunk_ids → document_registry.doc_id / chunk_registry.chunk_id | Semantic Search & Indexing → Document Ingestion Pipeline |

None of these are enforced at the database level — every one of them is an implicit reference
maintained entirely by application code. A document or chunk delete path (none exists today)
would need to account for all four by hand.

## Definition Drift

None found. `db/models.py` is the only schema definition for its three tables — there is no
separate DTO/validation layer that could disagree with it.

## Gaps

- No migration framework (Alembic or otherwise) — schema changes are unversioned; the only
  history is git history on `db/models.py`.
- Chroma and the BM25 index are created on demand, not pre-initialized, and their metadata
  shape is enforced only by `indexing/index_schema.py`'s `validate_metadata()` — nothing stops
  a caller from upserting a chunk missing a required field.
