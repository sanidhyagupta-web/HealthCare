# Product Spec — DICOM Loader

## Problem
The ingestion pipeline only accepts PDF and plain-text documents; `.dcm` (DICOM) files uploaded by radiologists are rejected, making imaging study metadata unsearchable.

## User & Use Case
- **Who is the user?** Radiologist or doctor uploading imaging studies for semantic search.
- **What are they trying to do?** Upload a DICOM file (X-ray, CT, MRI) so that its study metadata (modality, body part, referring physician, study description) is indexed and retrievable by other clinicians.
- **What happens today without this feature?** The upload page rejects `.dcm` files with an unsupported-extension error. Imaging study context is never searchable.

## Success Criteria
- [ ] A `.dcm` upload is accepted by the Streamlit upload page without error.
- [ ] The document reaches `DocStatus.INDEXED` following the same state machine as a typed PDF (`VALIDATED → PARSED → MARKDOWN_READY → CHUNKED → PII_PROCESSED → INDEXED`).
- [ ] DICOM header fields (Modality, StudyDescription, BodyPartExamined, InstitutionName, ReferringPhysicianName) appear in at least one indexed chunk and are retrievable via keyword search.
- [ ] PII fields (PatientID, PatientName, StudyDate, PatientBirthDate) are redacted to `[PATIENT_ID]`, `[PATIENT_NAME]`, `[DATE]` before any chunk is written to Chroma or BM25.
- [ ] DICOM-specific identifiers (Modality, StudyInstanceUID, SeriesInstanceUID) are stored as extra metadata on every chunk so they can be used for filtering.
- [ ] An audit log event is emitted when the DICOM file is parsed.
- [ ] Ingestion of a 1 MB `.dcm` file completes in < 5 seconds on a laptop (header-only; pixels are not read).

## Out of Scope
- Image pixel analysis, AI diagnosis, or any model inference on pixel data.
- Multi-frame DICOM series (multiple `.dcm` files per study) — only single-file uploads are supported in this version.
- DICOM SR (Structured Report) parsing — only standard modality headers.
- Retro-ingestion of existing `.dcm` files from PACS systems.

## HIPAA / Security Considerations
DICOM headers contain PHI: PatientName, PatientID, PatientBirthDate, ReferringPhysicianName, PerformingPhysicianName.
- [x] PII masking applied — all PHI fields pass through the existing PiiWorker (Presidio + regex); no bypass.
- [x] RBAC enforced — `allowed_roles` attached to every chunk via `rbac_policy.py`.
- [x] Audit logged — parse event written to `logs/audit.log`.
- [x] Encryption in place — raw `.dcm` bytes stored encrypted at rest; plain-text header never written to disk between ChunkingWorker and PiiWorker.

## Open Questions

| # | Question | Owner | Resolved? |
|---|---|---|---|
| 1 | Should multi-file DICOM series (multiple `.dcm` per study) be grouped into one doc_id? | Product | No — deferred to v2 |
| 2 | Is StudyInstanceUID sensitive enough to be treated as PII? | Compliance | No — it is a technical identifier with no direct patient link |
