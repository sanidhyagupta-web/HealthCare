# Technical Spec — DICOM Loader

## Architecture Decision
- [x] Ingestion — new parser type (`dicom`) added to the existing ParserWorker routing

No new worker or queue is needed. The DICOM file follows exactly the same path as a typed PDF: `parsing_queue → ParserWorker → markdown_queue → MarkdownWorker → chunking_queue → ...`

## Components Touched

| File / Module | Change type | Notes |
|---|---|---|
| `ingestion/parsers/dicom_parser.py` | **New** | Reads `.dcm` via pydicom (header only), returns text + DICOM metadata |
| `ingestion/parsers/doc_type_detector.py` | **New** | Detects `.dcm` extension (+ magic bytes) and routes to dicom_parser |
| `ingestion/markdown/dicom_converter.py` | **New** | Converts DICOM plain-text header dump to structured Markdown |
| `ingestion/markdown/__init__.py` | **New** | Package marker |
| `ingestion/parsers/__init__.py` | **New** | Package marker |
| `ingestion/__init__.py` | **New** | Package marker |
| `app/config.py` | Modify (future) | Add `SUPPORTED_EXTENSIONS` list that includes `.dcm` |
| `ui/streamlit_app.py` | Modify (future) | Add `.dcm` to `type=` argument of `st.file_uploader` |

## Data Model Changes

DICOM-specific identifiers are stored in chunk metadata (not as a new DB column) alongside the mandatory fields. The document registry row is unchanged — it stores `doc_id`, `source_file`, `status`, and timestamps as for any other document type.

```python
# Extra fields added to every chunk's metadata when doc_type == "dicom"
{
    "dicom_modality": "CT",
    "dicom_study_instance_uid": "1.3.6.1.4.1...",
    "dicom_series_instance_uid": "1.3.6.1.4.1...",
}
```

## API / Interface Surface

### `parse_dicom(file_bytes: bytes) -> dict`
```python
{
    "text": str,                      # plain-text header dump for MarkdownWorker
    "page_count": int,                # always 1
    "dicom_modality": str,            # e.g. "CT", "MR", "CR"
    "dicom_study_instance_uid": str,
    "dicom_series_instance_uid": str,
}
```

### `detect_doc_type(filename: str, file_bytes: bytes | None = None) -> str`
Returns one of: `"dicom"`, `"pdf_typed"`, `"pdf_scanned"`, `"text"`.
Raises `ValueError` on unsupported extension.

### `is_dicom(text: str) -> bool`
Returns `True` if text starts with the sentinel line `"DICOM Study"` (written by `dicom_parser`).

### `convert_dicom_to_markdown(text: str) -> str`
Returns a Markdown string with sections:
- `# DICOM Study Report`
- `## Study Information`
- `## Patient Information`
- `## Technical Identifiers`

### Queue message shape (unchanged)
The ParserWorker forwards the same message shape as for PDFs:
```python
{
    "doc_id": str,
    "s3_key": str,
    "text": str,             # from parse_dicom()["text"]
    "page_count": int,
    "dicom_modality": str,   # extra fields merged in when doc_type == "dicom"
    "dicom_study_instance_uid": str,
    "dicom_series_instance_uid": str,
}
```

## Skills Required
- `skills/document-ingestion.md` — upload validation, registry, queue wiring, BaseWorker retry pattern
- `skills/chunking-strategy.md` — entity-preserving chunker, inline handoff, no disk write
- `skills/pii-masking.md` — PatientName/PatientID/StudyDate treated as PII, `[ENTITY_TYPE]` placeholder format

## Non-Negotiables Checklist
- [x] PII redacted before any disk write of chunk content (inline queue handoff; pydicom `stop_before_pixels=True`)
- [x] `allowed_roles` present in all Chroma metadata
- [x] Audit log event emitted when DICOM is parsed
- [x] `update_status()` called at each stage transition (VALIDATED → PARSED → MARKDOWN_READY → ... → INDEXED)
- [x] No hardcoded credentials or patient IDs
- [x] BaseWorker retry pattern used (DICOM parser plugs into existing ParserWorker — no new worker needed)
- [x] `stop_before_pixels=True` passed to `pydicom.dcmread` — pixel data never loaded into memory

## Risks & Unknowns

| Risk | Likelihood | Mitigation |
|---|---|---|
| pydicom not in project venv | Medium | Add `pydicom` to requirements; version-pin to ≥ 2.4 |
| DICOM file missing expected tags (e.g. BodyPartExamined) | High | Use `getattr(ds, attr, None)` for all fields; omit blank rows from markdown |
| Malformed / truncated DICOM file | Low | Catch `pydicom.errors.InvalidDicomError`, raise `ValueError` to trigger BaseWorker DLQ |
| Very large DICOM with embedded SR or overlays | Low | `stop_before_pixels=True` skips pixel data regardless of file size |
