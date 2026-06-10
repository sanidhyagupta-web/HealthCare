# Implementation Plan — DICOM Loader

## Pre-work
- [x] Read `skills/document-ingestion.md` — upload validation, registry, queue wiring.
- [x] Read `skills/chunking-strategy.md` — inline handoff rule, no disk write between ChunkingWorker and PiiWorker.
- [x] Read `skills/pii-masking.md` — entity placeholder format, field classification.
- [x] Confirmed `pydicom` not yet in venv; must be installed.
- [x] No DB migration needed — DICOM metadata stored in chunk metadata, not a new registry column.

## Step 1 — DB / Config changes
- [x] No new DB columns. DICOM-specific fields (`dicom_modality`, `dicom_study_instance_uid`, `dicom_series_instance_uid`) stored in chunk metadata alongside the standard mandatory fields.
- [ ] When `app/config.py` is created: add `.dcm` to `SUPPORTED_EXTENSIONS` and add `pydicom` to requirements file.

## Step 2 — Core logic

- [x] **`ingestion/parsers/dicom_parser.py`** — `parse_dicom(file_bytes: bytes) -> dict`
  - `pydicom.dcmread(io.BytesIO(file_bytes), stop_before_pixels=True)`
  - Extracts 21 header fields; omits blank values.
  - Returns `text` (plain-text dump), `page_count=1`, and three DICOM metadata keys.
  - Raises `ValueError` on `InvalidDicomError` to trigger BaseWorker DLQ path.

- [x] **`ingestion/parsers/doc_type_detector.py`** — `detect_doc_type(filename, file_bytes=None) -> str`
  - `.dcm` → `"dicom"` (also validates DICOM magic bytes `b"DICM"` at offset 128 if bytes provided).
  - `.pdf` → `"pdf_typed"` (typed/scanned split done by ParserWorker separately).
  - `.txt`/`.text` → `"text"`.
  - All other extensions raise `ValueError`.

- [x] **`ingestion/markdown/dicom_converter.py`** — `is_dicom(text)` + `convert_dicom_to_markdown(text)`
  - `is_dicom`: checks for `"DICOM Study"` sentinel on first line.
  - `convert_dicom_to_markdown`: parses key:value lines → `_DicomData` dataclass → renders markdown with `## Study Information`, `## Patient Information`, `## Technical Identifiers` sections.

## Step 3 — Security & Compliance
- [x] PatientName, PatientID, PatientBirthDate, ReferringPhysicianName, PerformingPhysicianName included in the plain-text output → flow through PiiWorker (Presidio) unchanged.
- [x] `stop_before_pixels=True` ensures pixel data (which can be large and is not needed) is never loaded.
- [x] No raw text written to disk between ChunkingWorker and PiiWorker — inline queue handoff as per skill.
- [ ] When `security/audit_logger.py` is created: emit `DICOM_PARSED` event after `update_status(doc_id, DocStatus.PARSED)`.

## Step 4 — Queue wiring
- No new queue or worker. DICOM plugs into the existing ParserWorker via `doc_type_detector.py`.
- [ ] When `workers/parser_worker.py` is created: add branch `if doc_type == "dicom": result = parse_dicom(file_bytes)`.
- [ ] When `workers/markdown_worker.py` is created: add branch `if is_dicom(text): md = convert_dicom_to_markdown(text)`.
- [ ] When `workers/chunking_worker.py` is created: merge `dicom_modality`, `dicom_study_instance_uid`, `dicom_series_instance_uid` into each chunk's metadata dict.

## Step 5 — Tests
- [x] **`tests/unit/test_dicom_parser.py`**
  - Uses `pydicom.data.get_testdata_file("CT_small.dcm")` — no synthetic data.
  - Covers: required return keys, Modality value, is_dicom detection, markdown sections, UID propagation, doc_type_detector routing, invalid file error.

## Step 6 — Eval
- [ ] After pipeline workers are wired: seed one `.dcm` via `scripts/` and assert status = `INDEXED`.
- [ ] Update `evals/case-01-dicom-loader/result-notes.md` with outcome.

## Step 7 — Documentation
- [ ] Update `skills/document-ingestion.md` to add DICOM as a supported type.
- [ ] Add `pydicom>=2.4` to requirements file when created.

## Rollback plan
Remove the `".dcm"` branch from `detect_doc_type` and the `is_dicom` branch from the MarkdownWorker. Existing documents are unaffected. DICOM uploads will fail validation at the extension check and never reach the parsing queue.
