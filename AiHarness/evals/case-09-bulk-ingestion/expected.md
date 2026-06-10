# Eval Case 09 — Expected Output

## Templates
- [ ] `features/active/bulk-ingestion/01-product-spec.md` created and filled:
  - User: radiologist / clinic admin uploading end-of-day scan batch
  - Problem: uploading 50 documents one at a time through the single-file endpoint is impractical for batch workflows
  - Success criteria: `POST /ingest/bulk` accepts up to 50 files; returns immediately with per-file `queued`/`rejected` status; rejected files include reason; one batch-level audit event (not 50); roles doctor/nurse/admin accepted; others get 403
  - Out of scope: upload progress polling endpoint, resumable uploads, ZIP archive extraction

- [ ] `features/active/bulk-ingestion/02-technical-spec.md` created and filled:
  - Architecture decision: "Ingestion — entry point"
  - New route in `app/main.py`; unchanged workers/queues downstream
  - Skills referenced: `document-ingestion.md`, `audit-logging.md`, `access-control.md`
  - No data model changes — each file creates one `DocumentRegistry` row as normal

- [ ] `features/active/bulk-ingestion/03-implementation-plan.md` created and filled in correct step order

## Code: `app/main.py` additions

### `POST /ingest/bulk`
```python
@app.post("/ingest/bulk")
async def bulk_ingest(
    role: str = Header(...),
    files: list[UploadFile] = File(...),
):
    allowed = {"doctor", "nurse", "admin"}
    validated_role = get_role(role)   # from rbac_policy.py
    if validated_role not in allowed:
        raise HTTPException(403, "Insufficient role for bulk ingest")
    if len(files) > 50:
        raise HTTPException(422, "Maximum 50 files per batch")

    results = []
    accepted = 0
    rejected = 0
    for file in files:
        result = _process_single_upload(file)   # validate, register, encrypt, enqueue
        results.append(result)
        if result["status"] == "queued":
            accepted += 1
        else:
            rejected += 1

    log_event(
        "BULK_INGEST_SUBMITTED",
        details={"total": len(files), "accepted": accepted, "rejected": rejected},
    )
    return {"job_ids": results}
```

### `_process_single_upload(file)` (helper, not a new class)
```python
# Returns {"doc_id": str, "filename": str, "status": "queued"|"rejected", "reason": str|None}
# Validates: file extension in SUPPORTED_EXTENSIONS, file size <= 50MB
# On validation pass: create_document(), encrypt+S3 upload, queues.parsing_queue.put(...)
# On validation fail: return "rejected" with reason — does NOT raise exception (one file failure must not block others)
```
- `DocumentValidator` used for type/size checks — not inline if-else
- Each file independently validated — exception in one file caught and surfaced as `"rejected"`, loop continues
- `create_document()` called per file — each file gets its own `doc_id`

## Response shape exactly
```json
{
  "job_ids": [
    {"doc_id": "abc123", "filename": "scan1.pdf", "status": "queued", "reason": null},
    {"doc_id": null, "filename": "badfile.exe", "status": "rejected", "reason": "Unsupported file type"}
  ]
}
```
- Response returned immediately — does not wait for ingestion pipeline to complete
- `doc_id` is `null` for rejected files

## Conventions respected
- Downstream workers/queues unchanged — bulk endpoint feeds `queues.parsing_queue` same as single-file path
- `create_document()` called per accepted file — no batch registration shortcut
- `BULK_INGEST_SUBMITTED` single audit event covers the batch — not one event per file
- Role validated against `rbac_policy.py`

## Non-negotiables respected
- No raw filenames, patient data, or PHI in `BULK_INGEST_SUBMITTED` audit event details
- Rejected files never enqueued — they never enter the pipeline
- Duplicate files (same hash) rejected at `create_document()` time with reason `"Duplicate document"`
- No hardcoded role strings — validated against `rbac_policy.py`

## Tests expected
- Unit test: batch of 51 files returns 422
- Unit test: `role="billing"` returns 403
- Unit test: mixed batch (2 valid PDFs + 1 `.exe`) → response has 2 `queued`, 1 `rejected` with reason; only 2 items on `parsing_queue`
- Unit test: `BULK_INGEST_SUBMITTED` audit event contains `total`, `accepted`, `rejected` — not filenames
- Unit test: one file raises exception during `create_document()` → other files still processed (exception isolation)
- Integration test: 3-file batch → all 3 reach `DocStatus.INDEXED` after workers process queue

## What failing looks like
- Agent awaits ingestion completion before returning (blocks caller for minutes)
- Agent emits one `DOC_VALIDATED` audit event per file instead of one `BULK_INGEST_SUBMITTED` for the batch
- Agent lets a single file validation failure raise an unhandled exception, blocking remaining files
- Agent hardcodes `["doctor", "nurse", "admin"]` inline instead of reading from `rbac_policy.py`
- Agent creates a new queue (`bulk_queue`) instead of enqueuing directly to `queues.parsing_queue`
- Agent includes filenames in the audit event details (filenames may contain patient names)
