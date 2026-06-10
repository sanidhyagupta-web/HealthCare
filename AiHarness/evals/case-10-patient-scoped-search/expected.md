# Eval Case 10 — Expected Output

## Templates
- [ ] `features/active/patient-scoped-search/01-product-spec.md` created and filled:
  - User: doctor / nurse doing patient-specific clinical review
  - Problem: current search retrieves from all patients — "what is patient X's current medication?" returns results from multiple patients
  - Success criteria: `patient_id_hash` restricts retrieval to that patient's chunks at Chroma query level; non-clinical roles get 403; raw patient IDs never accepted; `PATIENT_SCOPED_QUERY` audit event emitted; unscoped search path unchanged
  - Out of scope: cross-patient cohort queries, patient consent tracking, patient self-service access

- [ ] `features/active/patient-scoped-search/02-technical-spec.md` created and filled:
  - Architecture decision: "Search / retrieval + Security / RBAC"
  - Modified: `app/main.py` (`SearchRequest` + route logic), `indexing/chroma_store.py` (add `where` filter support), `indexing/pii_entity_index.py` (hash lookup)
  - Skills referenced: `hybrid-search.md`, `pii-masking.md`, `access-control.md`, `audit-logging.md`
  - No data model changes — `patient_id` already in chunk metadata

- [ ] `features/active/patient-scoped-search/03-implementation-plan.md` created and filled in correct step order

## Code changes

### `app/main.py` — `SearchRequest` extended
```python
class SearchRequest(BaseModel):
    query: str
    role: str
    patient_id_hash: Optional[str] = None

    @validator("patient_id_hash")
    def validate_hash_format(cls, v):
        if v is not None and not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("patient_id_hash must be a 64-character hex SHA-256 string")
        return v
```
- Raw MRN / patient name / DOB never accepted — validator enforces 64-char hex only

### `app/main.py` — route logic
```python
if request.patient_id_hash is not None:
    if request.role not in {"doctor", "nurse"}:
        raise HTTPException(403, "Patient-scoped search requires clinical role")
    patient_scope = pii_entity_index.resolve_patient_scope(request.patient_id_hash)
    chroma_filter = {"patient_id": {"$eq": patient_scope}}
    audit_event = "PATIENT_SCOPED_QUERY"
else:
    chroma_filter = None
    audit_event = "QUERY_SUBMITTED"

vector_results = query_chunks(embedding, n_results=20, where=chroma_filter)
# BM25 also filtered by patient_id when chroma_filter is set
```
- Role check happens before any retrieval — not after
- `audit_event` variable used so audit log correctly labels scoped vs unscoped queries
- Unscoped path (`patient_id_hash=None`) identical to before — no behavior change

### `indexing/chroma_store.py` (modified)
```python
def query_chunks(embedding, n_results=20, where: Optional[dict] = None) -> list[dict]:
    kwargs = {"query_embeddings": [embedding], "n_results": n_results}
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)
```
- `where` filter applied at Chroma query level — not post-retrieval filtering
- Signature change is backward-compatible (default `where=None`)

### `indexing/pii_entity_index.py` (modified)
```python
def resolve_patient_scope(patient_id_hash: str) -> str:
    # Looks up hash in pii_entity_index
    # Returns the value stored at index time (hashed patient_id used in chunk metadata)
    # Raises PatientNotFoundError if hash not in index
```
- Hash lookup goes through `pii_entity_index` — no inline DB query in route handler
- Never returns raw patient name or MRN — returns the form stored in chunk metadata

### `audit-logging` — `PATIENT_SCOPED_QUERY` event
```python
log_event(
    "PATIENT_SCOPED_QUERY",
    user_id=caller_user_id,
    doc_id=None,
    query_hash=hash_query(request.query),
    details={"patient_id_hash": request.patient_id_hash, "role": request.role},
)
```
- `patient_id_hash` in details (acceptable — it's a hash, not raw PHI)
- Raw query text not logged — only `query_hash`

## Conventions respected
- `filter_results_by_role` still called after retrieval — patient scope narrows candidates, role filter still enforces permissions
- `apply_role_mask` still called — patient-scoped results still masked per role
- `generate_answer()` still called through `llm/claude_client.py` — no new LLM call paths
- `pii_entity_index.py` is the single lookup point — no inline hash comparisons in routes

## Non-negotiables respected
- Raw patient ID / MRN / name never accepted as input — 422 on non-hex or wrong-length hash
- `PATIENT_SCOPED_QUERY` audit event logged (not silently treated as `QUERY_SUBMITTED`)
- Non-clinical roles (admin, billing, researcher, anonymous) get 403 when `patient_id_hash` provided
- Unscoped search path unchanged — existing callers unaffected

## Tests expected
- Unit test: `patient_id_hash="John Smith"` → 422 (not a hex string)
- Unit test: `patient_id_hash="abc123"` (too short) → 422
- Unit test: `patient_id_hash=<valid 64-char hex>` with `role="admin"` → 403
- Unit test: `patient_id_hash=<valid hash>` with `role="doctor"` → `query_chunks` called with `where={"patient_id": ...}`
- Unit test: `patient_id_hash=None` → `query_chunks` called with `where=None` (unscoped path unchanged)
- Unit test: `PATIENT_SCOPED_QUERY` audit event includes `patient_id_hash` in details, not raw patient name
- Integration test: two patients' documents seeded; patient-scoped search returns only the target patient's chunks

## What failing looks like
- Agent accepts raw MRN or patient name as `patient_id_hash` (no format validation)
- Agent filters by `patient_id` after retrieval (post-retrieval instead of Chroma `where` filter)
- Agent allows `role="admin"` to perform patient-scoped search (admin is not a clinical role)
- Agent emits `QUERY_SUBMITTED` instead of `PATIENT_SCOPED_QUERY` (scoped queries indistinguishable in audit trail)
- Agent does hash lookup inline in the route handler instead of via `pii_entity_index.py`
- Agent changes unscoped search path (existing callers break)
- Agent skips `filter_results_by_role` because patient scope is already applied (RBAC and patient scope are orthogonal — both must run)
