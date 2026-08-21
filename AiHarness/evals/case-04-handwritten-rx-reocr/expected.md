# Eval Case 04 — Expected Output

## Templates
- [ ] `features/active/handwritten-rx-reocr/01-product-spec.md` created and filled:
  - User: doctor / pharmacist reviewing handwritten prescription scans
  - Problem: Tesseract fails on low-quality scans (confidence < 0.40), producing garbage text or empty extractions
  - Success criteria include: document with Tesseract confidence < 0.40 still reaches `DocStatus.INDEXED`; `LOW_CONFIDENCE_OCR` audit event emitted with confidence score; `RX_HEADER`+`MEDICATION`+`DOSAGE_FREQ` blocks intact in final chunks
  - Out of scope: general image understanding, non-prescription document vision OCR, cloud Vision APIs
  - HIPAA: Qwen call is local (no external API); PHI still passes through PiiWorker before indexing

- [ ] `features/active/handwritten-rx-reocr/02-technical-spec.md` created and filled:
  - Architecture decision: "Ingestion — parser tier" (not a new worker/queue)
  - New file: `ingestion/parsers/vision_ocr.py`
  - Modified file: `workers/parser_worker.py` (add confidence check + fallback branch)
  - Modified file: `app/config.py` or `settings.py` (add `ocr_confidence_threshold = 0.40`)
  - Skills referenced: `document-ingestion.md`, `chunking-strategy.md`, `audit-logging.md`
  - Non-negotiables: no external API calls, PHI not on disk before PiiWorker, BaseWorker retry pattern unchanged

- [ ] `features/active/handwritten-rx-reocr/03-implementation-plan.md` created and filled in correct step order

## Files created / modified

### `app/config.py` or `settings.py`
```python
ocr_confidence_threshold: float = 0.40
```
Must come from config — not hardcoded in `parser_worker.py`.

### `ingestion/parsers/vision_ocr.py` (new file)
```python
def extract_text_with_vision(file_bytes: bytes) -> str:
    # Loads Qwen/Qwen2-VL-2B-Instruct locally (transformers pipeline)
    # Returns plain text — same shape as Tesseract output
    # Raises VisionOCRError on model load failure or empty output
```
- Model loaded once at module level, not per-call
- No external API — local `transformers` pipeline only
- Returns plain string (same contract as `pdf_parser.py` text return)

### `workers/parser_worker.py` (modified)
```python
if doc_type == "pdf_scanned":
    text, confidence = tesseract_extract(file_bytes)
    if confidence < settings.ocr_confidence_threshold:
        log_event("LOW_CONFIDENCE_OCR", doc_id=doc_id, details={"confidence": confidence, "fallback": "qwen_vision"})
        text = vision_ocr.extract_text_with_vision(file_bytes)
```
- Confidence threshold read from `settings.ocr_confidence_threshold`
- `LOW_CONFIDENCE_OCR` audit event emitted before fallback (not after)
- Fallback result passed to markdown queue — same path as normal parse

## Entity preservation verified
- Chunker must not split `RX_HEADER` + `MEDICATION` + `DOSAGE_FREQ` + `DRUG_DOSE` blocks
- Implementation plan must reference `chunking-strategy.md` and call out these entity types explicitly
- Technical spec must note no new chunker is introduced — `entity_preserving_chunker` handles these already

## Conventions respected
- `vision_ocr.py` follows same return shape as other parsers (plain text string)
- Model loaded at module import, not inside `extract_text_with_vision()`
- `update_status(doc_id, DocStatus.PARSED)` called after successful vision extraction
- Fallback path forwards to `queues.markdown_queue` — no new queue

## Non-negotiables respected
- No external API calls (Qwen model is local)
- No hardcoded threshold — `settings.ocr_confidence_threshold` used
- PHI not written to disk between vision OCR output and PiiWorker
- `LOW_CONFIDENCE_OCR` event uses `log_event()` from `security/audit_logger.py`

## Tests expected
- Unit test: `extract_text_with_vision(prescription_bytes)` returns non-empty string containing drug name
- Unit test: when Tesseract confidence = 0.30 (< threshold), `parser_worker` calls vision OCR and emits `LOW_CONFIDENCE_OCR`
- Unit test: when Tesseract confidence = 0.80 (≥ threshold), `parser_worker` does NOT call vision OCR
- Unit test: `LOW_CONFIDENCE_OCR` audit event includes `confidence` in details dict
- Integration test: prescription `.pdf` with confidence < 0.40 reaches `DocStatus.INDEXED` with intact `MEDICATION` entity group in chunks

## What failing looks like
- Agent hardcodes `0.40` in `parser_worker.py` instead of reading from settings
- Agent calls an external Vision API (OpenAI GPT-4V, Google Vision) instead of local Qwen
- Agent loads the Qwen model inside `extract_text_with_vision()` (called per document — catastrophic performance)
- Agent creates a new `VisionWorker` queue stage instead of branching inside `ParserWorker`
- Agent lets vision OCR output bypass PiiWorker (PHI written to disk)
- Chunker splits `MEDICATION: Metformin 500mg` away from `DOSAGE_FREQ: twice daily` across chunk boundary
