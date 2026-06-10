# Technical Spec — Bulk Ingestion

## Architecture Decision
- [x] Ingestion — entry point (new route; unchanged workers/queues downstream)

## Components Touched

| File / Module | Change type | Notes |
|---|---|---|
| `app/main.py` | New FastAPI app instance + `POST /ingest/bulk` route + `_process_single_upload_bytes` helper | Existing `ingest_document()` untouched |
| `ingestion/validator.py` | New `DocumentValidator` class; new `SUPPORTED_EXTENSIONS` constant | Works on in-memory bytes, not file paths |
| `ingestion/registry.py` | New `is_duplicate_document(filename)` helper | Filename-based duplicate guard (no schema change) |
| `ingestion/metadata/rbac_policy.py` | New `_INGEST_ALLOWED_ROLES` constant + `get_ingest_allowed_roles()` function | Single source of truth for upload RBAC |
| `ui/bulk_upload_page.py` | New Streamlit page | Calls `_process_single_upload_bytes` directly (no HTTP) |
| `ui/streamlit_app.py` | Add "Bulk Upload" nav item | Routes to `bulk_upload_page.render()` |
| `requirements.txt` | Add `fastapi`, `python-multipart`, `uvicorn` | Required for HTTP endpoint |
| `tests/unit/test_bulk_ingestion.py` | New unit test file | Covers 422, 403, mixed batch, audit event, isolation |

## Data Model Changes
None — each accepted file creates one `DocumentRegistry` row via the existing `register_document()` call.

## API / Interface Surface

### HTTP endpoint
```
POST /ingest/bulk
Headers:
  role: str           # doctor | nurse | admin (required)
  uploader-id: str    # default "anonymous"
  patient-id: str     # default "UNKNOWN"
  department: str     # default "general"
Body: multipart/form-data, field name "files", up to 50 files

Response 200:
{
  "job_ids": [
    {"doc_id": "abc123", "filename": "scan1.pdf", "status": "queued",   "reason": null},
    {"doc_id": null,     "filename": "bad.exe",   "status": "rejected", "reason": "Unsupported file type: '.exe'"}
  ]
}

Response 403: role not in INGEST_ALLOWED_ROLES
Response 422: more than 50 files
```

### New Python helper (callable from both HTTP endpoint and Streamlit UI)
```python
def _process_single_upload_bytes(
    filename: str,
    content: bytes,
    uploader_id: str,
    patient_id: str,
    department: str,
) -> dict:
    # Returns {"doc_id": str|None, "filename": str, "status": "queued"|"rejected", "reason": str|None}
    # Never raises — all exceptions caught and surfaced as "rejected"
```

## Skills Required
- `skills/document-ingestion.md`
- `skills/audit-logging.md`
- `skills/access-control.md`

## Non-Negotiables Checklist
- [x] PII redacted before any disk write of chunk content — accepted files enter existing worker pipeline unchanged
- [x] `allowed_roles` present in all Chroma metadata — PiiWorker sets this downstream
- [x] Audit log event emitted — single `BULK_INGEST_SUBMITTED` per batch (not per file)
- [x] `update_status()` called after `register_document()` to set `DocStatus.VALIDATED`
- [x] No hardcoded credentials or patient IDs
- [x] No hardcoded role lists — `get_ingest_allowed_roles()` in `rbac_policy.py` is the single source

## Risks & Unknowns

| Risk | Likelihood | Mitigation |
|---|---|---|
| S3 unavailable mid-batch | Low | Per-file exception isolation returns "rejected" for that file; others proceed |
| Very large files (50 MB × 50) held in memory | Medium | Bytes read one file at a time inside the loop; no concurrent buffering |
| Department "radiology" missing from rbac_policy | High | Add "radiology" and "oncology" to `_DEPARTMENT_ROLES` as part of this change |
