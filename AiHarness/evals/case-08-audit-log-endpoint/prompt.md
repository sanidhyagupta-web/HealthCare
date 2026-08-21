# Eval Case 08 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

The compliance team needs a queryable audit log API so they can investigate access incidents without reading raw log files.

Build a `GET /admin/audit-logs` endpoint with the following behaviour:
- Accepts optional query parameters: `user_id`, `event_type`, `doc_id`, `from_date` (ISO 8601), `to_date` (ISO 8601), `limit` (default 100, max 1000).
- Reads from the `AuditLog` SQLAlchemy table — not from `logs/audit.log`.
- Returns a JSON array of audit records. Each record must include: `event_type`, `user_id`, `doc_id`, `query_hash`, `timestamp`, `details`.
- Must never return raw query text, raw PHI, patient names, MRNs, or any fields not present on the `AuditLog` model. If `details` contains any field matching a known PII pattern, replace it with `[REDACTED]` in the response.
- Restrict access to `admin` role only. Return 403 for any other role. Return 401 if no role header is provided.
- Emit its own `AUDIT_LOG_QUERIED` event every time the endpoint is called, logging the `admin` user_id and the filter parameters used (not the results).

The endpoint must not expose a way to reconstruct patient queries — `query_hash` is acceptable, raw query text is not.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.
