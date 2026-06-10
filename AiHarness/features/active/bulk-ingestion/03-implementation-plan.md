# Implementation Plan — Bulk Ingestion

## Pre-work
- [x] Read `skills/document-ingestion.md`, `skills/audit-logging.md`, `skills/access-control.md`.
- [x] Confirmed no new `app/config.py` keys needed (`max_file_size_bytes` = 50 MB already set).
- [x] Confirmed no DB migration needed — no new columns/tables.

## Step 1 — DB / Config changes
No schema changes. No new config keys.

## Step 2 — Core logic

- [x] Add `get_ingest_allowed_roles()` to `ingestion/metadata/rbac_policy.py` — single source of truth for upload RBAC.
- [x] Add `SUPPORTED_EXTENSIONS` constant and `DocumentValidator` class to `ingestion/validator.py` — validates in-memory bytes without touching the filesystem.
- [x] Add `is_duplicate_document(filename)` to `ingestion/registry.py` — returns True if a non-failed document with the same filename already exists.
- [x] Add FastAPI `app` instance, `_process_single_upload_bytes()` helper, and `POST /ingest/bulk` endpoint to `app/main.py`. Existing `ingest_document()` is untouched.

## Step 3 — Security & Compliance
- [x] `_process_single_upload_bytes` uploads bytes to S3 via `storage.s3_client.upload()` (KMS-encrypted) before any registry write.
- [x] `BULK_INGEST_SUBMITTED` audit event contains only aggregate counts — no filenames, no patient data.
- [x] Role validated against `get_ingest_allowed_roles()` from `rbac_policy.py` — no inline hardcoded role lists.
- [x] Rejected files never enqueued — `queues.parsing_queue.put()` only called after successful S3 upload + registry write.

## Step 4 — Queue wiring
No new queues. Accepted files are enqueued onto the existing `queues.parsing_queue` with the same message shape as `ingest_document()`.

## Step 5 — Tests
- [x] Unit: batch of 51 files → HTTP 422.
- [x] Unit: `role="billing"` → HTTP 403.
- [x] Unit: mixed batch (2 valid PDFs + 1 `.exe`) → 2 `queued`, 1 `rejected`; only 2 items on `parsing_queue`.
- [x] Unit: `BULK_INGEST_SUBMITTED` audit event `details` contains `total`, `accepted`, `rejected` — no filenames.
- [x] Unit: exception in `register_document()` for one file → other files still processed (isolation).

## Step 6 — Eval
No retrieval behavior changed. Integration test: 3-file batch → all 3 reach `DocStatus.INDEXED` (requires live workers + S3 — run separately with `pytest -m integration`).

## Step 7 — Documentation
- [x] Feature spec files in `features/active/bulk-ingestion/`.
- [x] `requirements.txt` updated with `fastapi`, `python-multipart`, `uvicorn`.
- [x] Run with: `uvicorn app.main:app --reload` (API) or `streamlit run ui/streamlit_app.py` (UI).

## Rollback plan
Remove the `@app.post("/ingest/bulk")` route and the `_process_single_upload_bytes` helper from `app/main.py`. The `ingest_document()` function and all downstream workers are unchanged.
