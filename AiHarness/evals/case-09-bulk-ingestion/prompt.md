# Eval Case 09 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

The radiology department needs to upload batches of up to 50 documents at once (mixed PDF, text, and DICOM files). The current Streamlit UI only handles single-file uploads.

Build a bulk ingestion endpoint:
- Add `POST /ingest/bulk` to `app/main.py`. The endpoint accepts a multipart form with up to 50 files.
- For each file: validate the file type and size (max 50 MB per file), register it in `DocumentRegistry` with `DocStatus.VALIDATED`, encrypt and upload to S3, then enqueue onto `queues.parsing_queue`.
- Each file is processed independently — one file's parse failure must not block other files in the batch.
- Return a response immediately (do not wait for ingestion to complete): `{"job_ids": [{"doc_id": str, "filename": str, "status": "queued" | "rejected", "reason": str | null}]}`.
- Rejected files (wrong type, too large, duplicate) must include a `reason` and must NOT be enqueued.
- Emit a `BULK_INGEST_SUBMITTED` audit event once per batch (not once per file). The event `details` must include total file count, accepted count, and rejected count — not individual filenames or patient data.
- The endpoint must be accessible to `doctor`, `nurse`, and `admin` roles. Reject other roles with 403.
- Add frontend for the same seperately in the Streamlit UI. 

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.
