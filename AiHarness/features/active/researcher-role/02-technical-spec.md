# Technical Spec — Researcher Role

## Architecture Decision
- [x] Security / RBAC (new role, masking rule, and permission)

## Components Touched

| File / Module | Change type | Notes |
|---|---|---|
| `ingestion/metadata/rbac_policy.py` | Add role to departments | Add `researcher` to `general` and `cardiology` allowed_roles |
| `ingestion/pii/role_based_masking.py` | New masking rule | `RESEARCHER_MASKED_ENTITIES` set; extend `apply_role_mask` dispatch |
| `security/access_control.py` | Existing pattern | `filter_results_by_role` unchanged — RBAC filter already works by `allowed_roles` list membership |
| `tests/unit/test_researcher_role.py` | New tests | Unit + integration tests for masking and RBAC |

## Data Model Changes
None. `allowed_roles` is already a list field on every chunk's metadata. Adding `researcher` to `rbac_policy.py` automatically includes it when new chunks are ingested from `general`/`cardiology` departments.

## API / Interface Surface

No new API surface. The existing search pipeline call order is unchanged:

```
filter_results_by_role(results, user_role)   ← RBAC (unchanged)
  → apply_role_mask(chunks, user_role)        ← PII masking (researcher rule added)
  → generate_answer(query, masked_chunks)     ← LLM
  → log_event("QUERY_SUBMITTED", ...)         ← Audit
```

New masking rule signature:
```python
# ingestion/pii/role_based_masking.py
RESEARCHER_MASKED_ENTITIES: frozenset[str]  # entity types to redact for researcher
apply_role_mask(chunk: dict, role: str) -> dict  # existing signature, extended dispatch
```

## Skills Required
- `skills/access-control.md`
- `skills/pii-masking.md`

## Non-Negotiables Checklist
- [x] PII redacted before any disk write of chunk content — no change, ingest-time redaction is unchanged
- [x] `allowed_roles` present in all Chroma metadata — unchanged; `researcher` added via `rbac_policy.py`
- [x] Audit log event emitted for every search event — unchanged; `QUERY_SUBMITTED` already fires
- [x] `update_status()` called at each stage transition — not applicable, no new ingestion stage
- [x] No hardcoded credentials or patient IDs
- [x] Role string `"researcher"` defined only in `rbac_policy.py` and `role_based_masking.py`, never inline elsewhere

## Risks & Unknowns

| Risk | Likelihood | Mitigation |
|---|---|---|
| Existing chunks for general/cardiology don't include `researcher` in `allowed_roles` | High (pre-existing chunks) | Filter uses list membership at query time; `get_allowed_roles` is authoritative — but chunks must be re-indexed to pick up the new policy for existing docs |
| Researcher sees `[DATE]` tokens that could re-identify a patient in a small cohort | Low | Masking DATE is the safe default per HIPAA Safe Harbor rule |
