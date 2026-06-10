# Eval Case 01 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

We need to add support for DICOM image files (`.dcm`) as a new document type in the Harmony ingestion pipeline. A DICOM file contains a medical image (X-ray, MRI, CT scan) plus a structured header with patient metadata (PatientID, StudyDate, Modality, BodyPartExamined, etc.).

The feature should:
- Accept `.dcm` uploads through the existing Streamlit upload page.
- Extract the DICOM header fields into structured text (not the image pixels — we don't need image analysis yet).
- Convert the header metadata to the same Markdown format the MarkdownWorker produces.
- Pass the result through the existing chunking, PII, embedding, and indexing pipeline unchanged.
- Store the DICOM-specific fields (Modality, StudyInstanceUID, SeriesInstanceUID) as extra chunk metadata.

A DICOM file should reach `DocStatus.INDEXED` following exactly the same state machine as a typed PDF.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`
