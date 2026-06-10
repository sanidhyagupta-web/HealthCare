# Eval Case 06 — Expected Output

## Templates
- [ ] `features/active/dlq-retry-handling/01-product-spec.md` created and filled:
  - User: platform engineer / on-call operator
  - Problem: failed documents are invisible — no way to observe failures, retry them, or tell which pipeline stage broke
  - Success criteria: `DOC_FAILED` audit event on DLQ routing; admin endpoint returns failed documents; retry endpoint re-queues at correct stage; non-admin callers get 403
  - Out of scope: automatic retry scheduling, Slack/email alerting, UI for retries

- [ ] `features/active/dlq-retry-handling/02-technical-spec.md` created and filled:
  - Architecture decision: "Ingestion — worker infrastructure"
  - Modified: `workers/base_worker.py`; new: `queues.py` (add `dlq`); new routes in `app/main.py`
  - Skills referenced: `document-ingestion.md`, `audit-logging.md`
  - No data model changes — `retry_count` already on `DocumentRegistry`; new column: `failed_stage` (string)

- [ ] `features/active/dlq-retry-handling/03-implementation-plan.md` created and filled in correct step order

## Files created / modified

### `queues.py`
```python
dlq: queue.Queue = queue.Queue()
```
`dlq` is a `queue.Queue`, not a database table or list.

### `workers/base_worker.py`
```python
def handle_failure(self, message: dict, exc: Exception) -> None:
    doc_id = message["doc_id"]
    retry_count = increment_retry_count(doc_id)          # updates DocumentRegistry
    if retry_count < settings.max_retries:
        self.input_queue.put(message)                     # re-enqueue same stage
    else:
        update_status(doc_id, DocStatus.FAILED)
        update_failed_stage(doc_id, self.worker_name)     # writes failed_stage column
        queues.dlq.put(message)
        log_event(
            "DOC_FAILED",
            doc_id=doc_id,
            details={
                "worker_name": self.worker_name,
                "error_type": type(exc).__name__,
                "retry_count": retry_count,
                "stage": self.worker_name,
            },
        )
```
- `log_event` uses `security/audit_logger.py` — not a new logger
- `DOC_FAILED` event includes all four required detail keys

### `db/models.py` (modified)
- New nullable `failed_stage: str` column on `DocumentRegistry`

### `app/main.py` — two new routes

#### `GET /admin/failed-documents`
```python
@app.get("/admin/failed-documents")
def list_failed(role: str = Header(...)):
    if role != "admin":
        raise HTTPException(403)
    rows = get_failed_documents()   # queries DocumentRegistry for DocStatus.FAILED
    return [
        {"doc_id": r.doc_id, "source_file": r.source_file,
         "stage": r.failed_stage, "error_type": r.error_type,
         "retry_count": r.retry_count, "failed_at": r.updated_at}
        for r in rows
    ]
```
- Role validation against `rbac_policy.py` — not hardcoded `"admin"` string inline
- Returns only the six specified fields — no raw text, PHI, or chunk content

#### `POST /admin/retry-document/{doc_id}`
```python
@app.post("/admin/retry-document/{doc_id}")
def retry_document(doc_id: str, role: str = Header(...)):
    if role != "admin":
        raise HTTPException(403)
    doc = get_document(doc_id)
    reset_retry_count(doc_id)
    update_status(doc_id, DocStatus.VALIDATED)
    stage_queue = _stage_to_queue(doc.failed_stage)   # maps worker name → queue
    stage_queue.put({"doc_id": doc_id, ...})
    log_event("DOC_RETRY_REQUESTED", doc_id=doc_id, details={"stage": doc.failed_stage})
```
- Re-enqueues at `failed_stage`, not from parsing start
- Emits `DOC_RETRY_REQUESTED` audit event

## Conventions respected
- DLQ is `queue.Queue` on `queues.dlq` — not a DB table
- All workers call `self.handle_failure()` on exception — not custom per-worker retry logic
- `log_event()` called from `security/audit_logger.py`

## Non-negotiables respected
- No raw clinical text or PHI in `DOC_FAILED` audit event details
- Admin role validated against `rbac_policy.py`
- `retry_count` not reset silently — explicit `DOC_RETRY_REQUESTED` audit event

## Tests expected
- Unit test: `handle_failure()` with `retry_count=0` re-enqueues message on same queue
- Unit test: `handle_failure()` with `retry_count=2` (third failure) routes to `queues.dlq` and sets `DocStatus.FAILED`
- Unit test: `DOC_FAILED` audit event includes `worker_name`, `error_type`, `retry_count`, `stage`
- Unit test: `GET /admin/failed-documents` with `role="nurse"` returns 403
- Unit test: `GET /admin/failed-documents` with `role="admin"` returns list of failed documents
- Unit test: `POST /admin/retry-document/{doc_id}` re-enqueues on correct stage queue and emits `DOC_RETRY_REQUESTED`

## What failing looks like
- Agent stores DLQ messages in a new `FailedDocuments` DB table instead of `queue.Queue`
- Agent resets retry to parsing start instead of `failed_stage`
- Agent logs raw error message containing PHI in `DOC_FAILED` details
- Agent hardcodes `"admin"` in route handler instead of validating against `rbac_policy.py`
- Agent emits no audit event on retry — retry becomes invisible in audit trail
- Agent creates a new `logger.error()` call instead of using `log_event()` from `audit_logger.py`
