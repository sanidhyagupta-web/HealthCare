# Eval Case 03 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

Add a new `researcher` role to the Harmony system. A researcher is an academic studying de-identified patient outcomes — they should be able to search and retrieve document chunks, but must never see any patient-identifying information: no names, MRNs, dates of birth, or contact details. They CAN see diagnosis codes, lab values, medication names, and vital signs.

The feature should:
- Register `researcher` as a valid role in the RBAC policy.
- Allow `researcher` access to documents in the `general` and `cardiology` departments.
- Apply a masking rule that removes `PATIENT_NAME`, `MRN`, `DATE`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `SSN`, and `PATIENT_DEMOGRAPHICS` entity types from chunks returned to a researcher, while leaving `ICD10`, `LAB_VALUE`, `VITAL_SIGN`, `MEDICATION`, `DOSAGE_FREQ` visible.
- Ensure that the existing `POST /search` endpoint (or equivalent search flow) correctly enforces this masking when `role=researcher`.
- Add a test that verifies a researcher cannot retrieve any chunk containing an unmasked `[PATIENT_NAME]` or `[MRN]` placeholder.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.