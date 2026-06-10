# Skill: Document Ingestion

## What this covers
Uploading a medical document, encrypting it, detecting its type, registering it in the DB, and enqueuing it for parsing.

## Entry point
`workers/parser_worker.py` reads from `queues.parsing_queue`. Documents are enqueued there by the Streamlit upload page or `scripts/seed_mock_records.py`.

## Step sequence

1. **Validate** — check file extension, non-zero size, and that `doc_id` is unique in `DocumentRegistry`. Reject immediately if invalid; do not enqueue.
2. **Encrypt & upload** — upload raw bytes to S3 via `storage/s3_client.py`. KMS encryption is handled by the bucket policy. Store the `s3_key` in the registry row.
3. **Register** — call `ingestion/registry.py:create_document()` with `doc_id`, `source_file`, `status=VALIDATED`.
4. **Enqueue** — put `{"doc_id": ..., "s3_key": ..., "doc_type": "auto"}` on `queues.parsing_queue`.
5. **ParserWorker detects type** — `ingestion/parsers/doc_type_detector.py` inspects the file:
   - Typed PDF → `ingestion/parsers/pdf_parser.py` (PyMuPDF)
   - Scanned PDF → `ingestion/ocr/tesseract_ocr.py`; if OCR confidence < `settings.ocr_confidence_threshold` (0.40), fall back to Qwen Vision
   - Plain text → `ingestion/parsers/text_parser.py`
6. **Status update** — call `update_status(doc_id, DocStatus.PARSED)` after successful extraction.
7. **Forward** — put extracted text + metadata on `queues.markdown_queue`.

## BaseWorker retry pattern
All workers extend `workers/base_worker.py`. On exception: increment `retry_count`, re-enqueue if `retry_count < settings.max_retries` (3), else route to DLQ and set `status=FAILED`. Never swallow silently.

```python
# Good — follow BaseWorker pattern
class MyWorker(BaseWorker):
    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        # ... do work ...
        update_status(doc_id, DocStatus.SOME_STATUS)
        queues.next_queue.put({**message, "new_key": value})
```

## Bad examples the agent must avoid

```python
# BAD: hardcoded bucket name
s3.upload_file(path, "my-healthcare-bucket", key)

# BAD: writing unencrypted text to local disk between workers
with open(f"data/raw/{doc_id}.txt", "w") as f:
    f.write(extracted_text)

# BAD: silently continuing after parse failure
try:
    text = parse(path)
except Exception:
    pass  # never do this
```

## Failure modes seen
- Agent creates a new queue instead of using the existing `queues` module → breaks the worker chain.
- Agent writes extracted text to `data/processed/` before PII redaction → plaintext PHI on disk.
- Agent skips `create_document()` → document becomes invisible to status tracking and evals.

## Must NOT do
- Write unredacted text to any filesystem path between ChunkingWorker and PiiWorker.
- Create a new `DocumentRegistry` table or model — use `db/models.py`.
- Enqueue documents without a `doc_id` key.
