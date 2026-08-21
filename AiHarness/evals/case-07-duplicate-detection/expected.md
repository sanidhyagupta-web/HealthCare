# Eval Case 07 — Expected Output

## Templates
- [ ] `features/active/duplicate-detection/01-product-spec.md` created and filled:
  - User: clinical data engineer / admin
  - Problem: same document uploaded multiple times creates duplicate chunks in Chroma, inflating retrieval results with repeated content
  - Success criteria: exact re-upload reaches `DocStatus.DUPLICATE` immediately (no re-parse); all-duplicate-chunk doc reaches `DocStatus.DUPLICATE` after chunking; `DOC_DUPLICATE` audit event emitted; admin endpoint lists duplicates with original `doc_id`
  - Out of scope: near-duplicate / fuzzy matching, document versioning, automatic de-duplication of existing store

- [ ] `features/active/duplicate-detection/02-technical-spec.md` created and filled:
  - Architecture decision: "Ingestion — document registry"
  - Modified: `ingestion/registry.py`, `workers/chunking_worker.py`; new column `file_hash` on `DocumentRegistry`; new route `GET /admin/duplicate-documents` in `app/main.py`
  - Data model change: `file_hash VARCHAR(64)` column on `document_registry` table (nullable for legacy rows)
  - Skills referenced: `document-ingestion.md`, `chunking-strategy.md`, `audit-logging.md`

- [ ] `features/active/duplicate-detection/03-implementation-plan.md` created and filled in correct step order

## Files created / modified

### `db/models.py` (modified)
```python
file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
```
New `file_hash` column on `DocumentRegistry`. Nullable for backward compatibility with existing rows.

### `ingestion/registry.py` (modified)
```python
def create_document(doc_id: str, source_file: str, file_bytes: bytes, ...) -> DocumentRegistry:
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    existing = session.query(DocumentRegistry).filter_by(
        file_hash=file_hash, status=DocStatus.INDEXED
    ).first()
    if existing:
        new_doc = DocumentRegistry(
            doc_id=doc_id,
            file_hash=file_hash,
            status=DocStatus.DUPLICATE,
            original_doc_id=existing.doc_id,
        )
        session.add(new_doc)
        log_event("DOC_DUPLICATE", doc_id=doc_id, details={"original_doc_id": existing.doc_id})
        return new_doc
    # normal registration path continues...
```
- Hash computed from raw file bytes **before** parsing
- `DOC_DUPLICATE` event emitted immediately — document never enqueued for parsing
- New nullable `original_doc_id` column on `DocumentRegistry`

### `workers/chunking_worker.py` (modified)
After `register_chunk()` calls, check if all chunks were duplicates:
```python
if all_chunks_duplicate:
    update_status(doc_id, DocStatus.DUPLICATE)
    log_event("DOC_DUPLICATE", doc_id=doc_id, details={"reason": "all_chunks_duplicate"})
    return   # do not forward to pii_queue
```
- Uses existing `register_chunk()` return value or `ChunkRegistry` query — not a new mechanism
- Orphaned chunks not written to Chroma (forwarding to `pii_queue` skipped)

### `app/main.py` — new route

#### `GET /admin/duplicate-documents`
```python
@app.get("/admin/duplicate-documents")
def list_duplicates(role: str = Header(...)):
    if role != "admin":
        raise HTTPException(403)
    rows = get_duplicate_documents()  # DocStatus.DUPLICATE rows
    return [
        {"doc_id": r.doc_id, "source_file": r.source_file,
         "uploaded_at": r.created_at, "original_doc_id": r.original_doc_id}
        for r in rows
    ]
```

## Conventions respected
- `create_document()` is the single entry point for document registration — no inline hash check in route handler
- `register_chunk()` in `entity_preserving_chunker.py` unchanged — dedup flag surfaced to `ChunkingWorker` via return value or DB query
- `log_event()` called from `security/audit_logger.py`

## Non-negotiables respected
- File hash computed from bytes, not filename — filename-only check is trivially bypassed
- `DOC_DUPLICATE` audit event emitted for both level-1 (file hash) and level-2 (all-chunks) duplicates
- Admin-only endpoint validated against `rbac_policy.py`
- No raw file content or PHI in audit event details

## Tests expected
- Unit test: upload same file bytes twice → second doc reaches `DocStatus.DUPLICATE`, `original_doc_id` set
- Unit test: `DOC_DUPLICATE` audit event includes `original_doc_id` in details
- Unit test: `GET /admin/duplicate-documents` with `role="doctor"` returns 403
- Unit test: `create_document()` with renamed file but identical bytes → still detected as duplicate
- Integration test: document whose every chunk hashes to an existing chunk → `DocStatus.DUPLICATE`, no new Chroma upserts
- Integration test: document with at least one new chunk → NOT marked as duplicate, reaches `DocStatus.INDEXED`

## What failing looks like
- Agent checks filename or file size instead of SHA-256 of file bytes
- Agent marks the original document as `DUPLICATE` instead of the new upload
- Agent lets duplicate documents proceed through parsing and chunking (wastes compute, duplicates chunks in Chroma)
- Agent creates a new `DuplicateRegistry` table instead of adding a column to `DocumentRegistry`
- Agent emits no audit event for duplicate detection
- Agent leaves orphaned chunks in Chroma when all-chunk-duplicate path fires
