# Product Spec — Bulk Ingestion

## Problem
The Streamlit upload page and `POST /ingest` entry point only accept one document at a time; radiology staff need to upload end-of-day scan batches of up to 50 mixed files without manual repetition.

## User & Use Case
- **Who is the user?** Radiologist, doctor, nurse, or clinic admin uploading a batch of scan reports at end-of-day.
- **What are they trying to do?** Select up to 50 PDF, plain-text, or DICOM files in a single operation and have them all enqueued for ingestion in one request.
- **What happens today without this feature?** Users must upload files one at a time through the single-file endpoint. Uploading a 50-file batch takes ~50 sequential interactions and offers no batch-level status summary.

## Success Criteria
- [ ] `POST /ingest/bulk` accepts up to 50 files in a single multipart form request.
- [ ] The endpoint returns immediately (before ingestion completes) with per-file `queued` or `rejected` status and a `reason` for every rejected file.
- [ ] Files with unsupported extension, size > 50 MB, or duplicate filename are rejected with a human-readable reason and are never enqueued.
- [ ] Exactly one `BULK_INGEST_SUBMITTED` audit event is emitted per batch (not one per file); the event `details` contain `total`, `accepted`, and `rejected` counts only — no filenames or patient data.
- [ ] Roles `doctor`, `nurse`, `admin` are accepted; all other roles receive HTTP 403.
- [ ] A batch of 51 files returns HTTP 422.
- [ ] One file failing validation or encountering a processing error does not prevent the remaining files in the batch from being processed.
- [ ] The Streamlit UI exposes a dedicated Bulk Upload page with the same RBAC constraints as the API.

## Out of Scope
- Upload progress polling endpoint or resumable uploads.
- ZIP archive extraction — files must be submitted individually within the multipart form.
- Async worker status websocket/push.

## HIPAA / Security Considerations
- [x] PII masking applied — accepted files enter the existing 6-stage worker pipeline which runs PiiWorker before any chunk is indexed.
- [x] RBAC enforced — endpoint rejects roles not in `INGEST_ALLOWED_ROLES` from `rbac_policy.py`; 403 returned.
- [x] Audit logged — single `BULK_INGEST_SUBMITTED` event per batch with aggregate counts only; no filenames (filenames may contain patient names).
- [x] Encryption in place — raw bytes uploaded to S3 with KMS SSE before any registry entry is written.

## Open Questions

| # | Question | Owner | Resolved? |
|---|---|---|---|
| 1 | Should `patient_id` and `department` be per-file or per-batch? | Product | Per-batch (consistent with single-file endpoint) — Yes |
| 2 | Should the API endpoint require auth token or role header? | Eng | Role header (consistent with existing pattern) — Yes |
