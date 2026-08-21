# Eval Case 01 — Expected Output

## Templates
- [ ] `features/active/dicom-loader/01-product-spec.md` created and filled:
  - User: radiologist / doctor (states a specific role)
  - Success criteria include: document reaches `DocStatus.INDEXED`, DICOM header fields are searchable, PII fields (PatientID, PatientName, StudyDate) are redacted
  - HIPAA considerations checked

- [ ] `features/active/dicom-loader/02-technical-spec.md` created and filled:
  - Architecture decision: "Ingestion — new parser type"
  - `ingestion/parsers/dicom_parser.py` listed as new file
  - `doc_type_detector.py` listed as modified (add `.dcm` detection)
  - DB change: new column `dicom_series_id` or similar on `document_registry` (or stored in chunk metadata)
  - `app/config.py` change: optional `pydicom` dependency noted
  - Skills referenced: `document-ingestion.md`, `chunking-strategy.md`, `pii-masking.md`

- [ ] `features/active/dicom-loader/03-implementation-plan.md` created and filled in correct step order (DB → parser → security → queue → tests → eval)

## Files created
- `ingestion/parsers/dicom_parser.py` — reads `.dcm` via `pydicom`, extracts header fields, returns structured text
- `ingestion/parsers/doc_type_detector.py` — modified to detect `.dcm` extension and route to `dicom_parser`

## Conventions respected
- New parser follows the same return shape as `pdf_parser.py` (returns plain text that MarkdownWorker can process)
- `create_document()` called before parsing — document registered in registry
- `update_status(doc_id, DocStatus.PARSED)` called after successful DICOM header extraction
- DICOM-specific metadata (Modality, StudyInstanceUID) added to chunk metadata alongside required fields (`patient_id`, `source_file`, `allowed_roles`, etc.)
- Extracted PatientName and PatientID treated as PII — they pass through the normal PiiWorker path, not bypassed

## Non-negotiables respected
- No hardcoded patient IDs, bucket names, or KMS keys
- No fake DICOM data created inline to make tests pass — test uses a real `.dcm` fixture or pydicom's built-in test datasets
- Unredacted DICOM text not written to disk between chunking and PII stages
- `allowed_roles` present in Chroma metadata
- Audit log event emitted when DICOM is parsed

## Tests expected
- Unit test: `test_dicom_parser.py` — given a sample `.dcm` file, assert extracted text contains Modality and BodyPartExamined fields
- Integration test: seed one `.dcm` → assert final status is `DocStatus.INDEXED`
- PII test: assert PatientName in extracted text is redacted to `[PATIENT_NAME]` before indexing

## What failing looks like
- Agent writes extracted DICOM text to `data/processed/` before PII redaction
- Agent skips `doc_type_detector.py` and hardcodes the DICOM path in `run.py`
- Agent creates a separate DICOM queue instead of reusing `parsing_queue`
- Agent skips `register_chunk()` so DICOM chunks are not deduplicated
- Agent uses generic text splitter instead of `entity_preserving_chunker`
