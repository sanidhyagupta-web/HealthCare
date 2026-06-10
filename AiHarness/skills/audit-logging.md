# Skill: Audit Logging

## What this covers
What to log, when, in what format, and where — for HIPAA compliance.

## Implementation
`security/audit_logger.py` — all audit calls go through this module. It writes to **both** `logs/audit.log` (JSONL) and the `AuditLog` SQLAlchemy table (`db/models.py`).

```python
from security.audit_logger import log_event

log_event(
    event_type="QUERY_SUBMITTED",
    user_id=current_user.user_id,
    doc_id=None,          # None for query events
    query_hash=hash_query(query),
    details={"role": current_user.role, "result_count": len(results)},
)
```

## Required events

### Ingestion path
| Event | When to log |
|---|---|
| `DOC_VALIDATED` | Document passes validation |
| `DOC_PARSED` | ParserWorker completes successfully |
| `MARKDOWN_READY` | MarkdownWorker completes |
| `DOC_CHUNKED` | ChunkingWorker completes (include `chunk_count`, `duplicate_count`) |
| `PII_PROCESSED` | PiiWorker completes (include `entity_count`) |
| `DOC_EMBEDDED` | EmbeddingWorker completes |
| `DOC_INDEXED` | KeywordIndexWorker completes |
| `DOC_FAILED` | Any worker routes to DLQ (include `stage`, `error`) |

### Search path
| Event | When to log |
|---|---|
| `QUERY_SUBMITTED` | User submits query (log hash not raw text if query contains PII) |
| `RETRIEVAL_COMPLETE` | After RRF + rerank, before role filtering (log candidate count) |
| `RESULT_FILTERED` | After `filter_results_by_role` (log how many removed) |
| `ANSWER_GENERATED` | LLM response returned (log cited chunk IDs) |
| `ACCESS_DENIED` | `filter_results_by_role` removes all results |

## Log record format

```json
{
  "event_type": "QUERY_SUBMITTED",
  "user_id": "doctor_001",
  "doc_id": null,
  "query_hash": "sha256:...",
  "details": {"role": "doctor", "result_count": 5},
  "timestamp": "2026-05-24T10:30:00.000Z"
}
```

Never put raw query text, patient names, MRNs, or any PHI in `details`. Hash the query. Log chunk IDs not chunk text.

## Bad examples

```python
# BAD: logging raw query
log_event("QUERY_SUBMITTED", user_id=uid, details={"query": raw_query})

# BAD: logging only to file, skipping DB write
with open("logs/audit.log", "a") as f:
    f.write(json.dumps(event))

# BAD: skipping audit on "internal" calls
def _internal_search(query):
    # no log here — "it's internal"
    return retrieve(query)
```

## Failure modes seen
- Agent logs raw query text (contains patient names) — direct HIPAA violation.
- Agent adds a new logging utility instead of using `audit_logger.py` — DB write is skipped.
- Agent only logs on success — failures are invisible to compliance review.

## Must NOT do
- Log raw clinical text, raw PII, patient names, MRNs, DOBs, or query strings.
- Write audit logs only to file (DB write is required for queryability).
- Skip logging on any ingestion or search event, including failures.
- Use `print()` as a substitute for audit logging.
