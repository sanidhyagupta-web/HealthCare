# Eval Case 04 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

Some prescription scans in Harmony come in as low-quality handwritten images where Tesseract OCR returns a confidence score below 0.40. The current pipeline has no fallback — these documents silently fail or produce garbage text.

Add a fallback OCR path so that when `ParserWorker` detects a scanned PDF with Tesseract confidence < 0.40, it re-attempts extraction using the Qwen Vision model (`Qwen/Qwen2-VL-2B-Instruct`) instead.

The feature should:
- Add a confidence threshold check inside the scanned-PDF parse path in `workers/parser_worker.py`.
- If Tesseract confidence < 0.40, call a new `ingestion/parsers/vision_ocr.py` module that wraps the Qwen Vision model.
- The Qwen call must be local — no external APIs.
- The result from Qwen must pass through the same markdown conversion, entity-preserving chunking, PII redaction, embedding, and indexing steps as any other parsed document.
- Prescription documents often contain `RX_HEADER`, `MEDICATION`, `DOSAGE_FREQ`, and `DRUG_DOSE` entity groups — these must never be split across chunks by the chunker.
- Emit a `LOW_CONFIDENCE_OCR` audit event (with the Tesseract confidence score in `details`) when the fallback path is triggered.
- Add a config key `settings.ocr_confidence_threshold` (default `0.40`) so the threshold is not hardcoded.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.
