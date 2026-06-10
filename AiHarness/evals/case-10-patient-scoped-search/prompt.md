# Eval Case 10 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

Doctors need to restrict a search query to records belonging to a specific patient — for example, "what medications is patient X currently on?" without retrieving records from other patients.

Add patient-scoped search to the existing `POST /search` endpoint:
- Extend `SearchRequest` with an optional `patient_id_hash: str | None` field. This is a SHA-256 hash of the patient identifier — never the raw MRN or patient name.
- When `patient_id_hash` is provided, restrict vector and BM25 retrieval to chunks where the `patient_id` metadata field matches. Do this at the Chroma query level using a `where` filter — not post-retrieval filtering.
- Patient-scoped search is only available to `doctor` and `nurse` roles. If `patient_id_hash` is provided and the caller's role is not `doctor` or `nurse`, return a 403 with message `"Patient-scoped search requires clinical role"`.
- Never accept a raw patient name, MRN, or date-of-birth as a query parameter. The endpoint must validate that `patient_id_hash` is a 64-character hex string (SHA-256). Return 422 if it is not.
- Emit a `PATIENT_SCOPED_QUERY` audit event (instead of the usual `QUERY_SUBMITTED`) when `patient_id_hash` is provided. Include `patient_id_hash` in `details` — not the raw patient ID.
- The pii_entity_index lookup (resolving hash → patient scope) must go through `indexing/pii_entity_index.py` — not inline in the route handler.

Do not change the existing unscoped search path — `patient_id_hash=None` must behave exactly as before.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.
