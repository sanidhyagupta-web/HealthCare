# Product Spec — Researcher Role

## Problem
The system has no role for academic researchers, so de-identified clinical data cannot be shared with external researchers without granting them a clinical role that exposes patient-identifying information.

## User & Use Case
- **Who is the user?** Academic researcher (role: `researcher`)
- **What are they trying to do?** Query and retrieve de-identified clinical document chunks (diagnoses, lab values, medications, vital signs) for outcomes research.
- **What happens today without this feature?** Researchers must be granted `doctor` or `admin` access, exposing patient names, MRNs, and contact details — a HIPAA violation.

## Success Criteria

- [ ] A `researcher` user can search and retrieve chunks from `general` and `cardiology` departments.
- [ ] Chunks returned to `researcher` contain no `[PATIENT_NAME]`, `[MRN]`, `[DATE]`, `[PHONE_NUMBER]`, `[EMAIL_ADDRESS]`, `[SSN]`, or `[PATIENT_DEMOGRAPHICS]` tokens.
- [ ] `ICD10`, `LAB_VALUE`, `VITAL_SIGN`, `MEDICATION`, and `DOSAGE_FREQ` tokens remain visible to `researcher`.
- [ ] A `researcher` cannot retrieve chunks from the `billing` department.
- [ ] Audit log records a `QUERY_SUBMITTED` event when a researcher queries.
- [ ] No re-ingestion of existing documents is required — policy change takes effect at query time.

## Out of Scope
- Researcher write access or document upload.
- Fine-grained per-patient consent tracking.
- A dedicated researcher UI page.
- Access to the `billing` department.

## HIPAA / Security Considerations
- [x] PII masking applied — researcher masking rule added to `role_based_masking.py`
- [x] RBAC enforced — `researcher` added to `rbac_policy.py` for `general` and `cardiology` only
- [x] Audit logged — existing `QUERY_SUBMITTED` audit event covers researcher queries
- [x] Encryption in place — no change to at-rest encryption; masking is query-time only

## Open Questions

| # | Question | Owner | Resolved? |
|---|---|---|---|
| 1 | Should `researcher` see `DATE` tokens for non-identifying dates (e.g. lab draw dates)? | Product | No — safer to mask all DATE tokens per HIPAA Safe Harbor |
