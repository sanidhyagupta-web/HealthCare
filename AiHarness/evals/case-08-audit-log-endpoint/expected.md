# Eval Case 08 — Expected Output

## Templates
- [ ] `features/active/audit-log-endpoint/01-product-spec.md` created and filled:
  - User: compliance officer / admin
  - Problem: audit logs are JSONL flat files — not queryable by user, event type, or date range; incident investigation requires reading raw files
  - Success criteria: `GET /admin/audit-logs` returns filterable JSON from DB; no raw PHI or query text in response; admin-only; endpoint itself is audited
  - Out of scope: audit log export (CSV/PDF), log deletion, log amendment, real-time streaming

- [ ] `features/active/audit-log-endpoint/02-technical-spec.md` created and filled:
  - Architecture decision: "Observability / audit"
  - New route in `app/main.py`; reads from `AuditLog` SQLAlchemy table
  - Skills referenced: `audit-logging.md`, `access-control.md`
  - No schema changes — `AuditLog` table already exists

- [ ] `features/active/audit-log-endpoint/03-implementation-plan.md` created and filled in correct step order

## Code: `app/main.py` additions

### `GET /admin/audit-logs`
```python
@app.get("/admin/audit-logs")
def query_audit_logs(
    role: str = Header(...),
    user_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    doc_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
):
    if role != "admin":
        raise HTTPException(403, "Admin role required")
    if role is None:
        raise HTTPException(401, "Role header required")

    records = query_audit_log(
        user_id=user_id, event_type=event_type, doc_id=doc_id,
        from_date=from_date, to_date=to_date, limit=limit
    )
    sanitized = [sanitize_audit_record(r) for r in records]

    log_event(
        "AUDIT_LOG_QUERIED",
        user_id=caller_user_id,
        details={"filters": {"user_id": user_id, "event_type": event_type, "doc_id": doc_id}},
    )
    return sanitized
```

### `security/audit_logger.py` or `db/queries.py` (modified/new)
```python
def query_audit_log(user_id, event_type, doc_id, from_date, to_date, limit) -> list[AuditLog]:
    # SQLAlchemy query with optional filters
    # Reads from AuditLog table — not from logs/audit.log file

def sanitize_audit_record(record: AuditLog) -> dict:
    # Returns only: event_type, user_id, doc_id, query_hash, timestamp, details
    # Scans details dict for PII patterns (names, MRNs, phone, email, SSN)
    # Replaces matched values with [REDACTED]
```
- Query hits `AuditLog` DB table — not the JSONL file
- `details` field scanned for PII patterns using same regex as `pii_detector.py`
- Matched PII values in `details` replaced with `[REDACTED]` before returning

## Conventions respected
- Route uses `log_event()` from `security/audit_logger.py` to log itself — not `print()` or new logger
- `AUDIT_LOG_QUERIED` event logs filter parameters (not results)
- Role validated against `rbac_policy.py` — not hardcoded `"admin"` string inline
- Query reads from `AuditLog` SQLAlchemy model — not from JSONL file

## Non-negotiables respected
- Response never contains raw query text, patient names, MRNs, or other raw PHI
- `query_hash` field present (acceptable); raw query text absent
- 401 returned when role header is missing; 403 when role is not admin
- Endpoint is itself audited — `AUDIT_LOG_QUERIED` event emitted on every call

## Tests expected
- Unit test: `sanitize_audit_record()` replaces PII-matching strings in `details` with `[REDACTED]`
- Unit test: `sanitize_audit_record()` returns exactly the six specified fields — no extra columns
- Unit test: `GET /admin/audit-logs` with `role="nurse"` returns 403
- Unit test: `GET /admin/audit-logs` with no role header returns 401
- Unit test: `GET /admin/audit-logs` with `limit=1001` returns 422 (exceeds max)
- Unit test: `AUDIT_LOG_QUERIED` event is emitted after successful query, with filter params in details
- Integration test: `GET /admin/audit-logs?event_type=DOC_PARSED` returns only `DOC_PARSED` events

## What failing looks like
- Agent reads from `logs/audit.log` JSONL file instead of `AuditLog` DB table
- Agent returns raw `details` dict without PII scanning — raw query text or PHI leaks
- Agent does not emit `AUDIT_LOG_QUERIED` event (audit trail of audit access is missing)
- Agent creates a new `AuditQueryLogger` class instead of calling `log_event()`
- Agent allows `limit` parameter above 1000 (DoS risk)
- Agent returns all `AuditLog` columns including any raw-text fields not in the specified six
