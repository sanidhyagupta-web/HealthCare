# Eval Case 06 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

When a document fails processing (parse error, OCR error, embedding error) the current system has no observable retry or failure path. Operations cannot tell how many documents are stuck, why they failed, or how to retry them.

Build out the Dead Letter Queue (DLQ) and failure-handling path:
- All workers already extend `BaseWorker`. Ensure `BaseWorker.handle_failure()` increments `retry_count` on the `DocumentRegistry` row, re-enqueues the message if `retry_count < settings.max_retries` (3), and routes to `queues.dlq` with `DocStatus.FAILED` on the third failure.
- Emit a `DOC_FAILED` audit event every time a document is routed to the DLQ. The event `details` dict must include `worker_name`, `error_type`, `retry_count`, and `stage` (which pipeline stage failed).
- Add a `GET /admin/failed-documents` FastAPI endpoint that returns all documents with `DocStatus.FAILED`, including `doc_id`, `source_file`, `stage`, `error_type`, `retry_count`, and `failed_at`. This endpoint must be restricted to `admin` role only — return 403 for any other role.
- Add a `POST /admin/retry-document/{doc_id}` endpoint that resets `retry_count` to 0 and re-enqueues the document at the stage where it failed (not from the beginning). Admin role only.
- The DLQ must be a real `queue.Queue` on `queues.dlq`, not a database table.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.
