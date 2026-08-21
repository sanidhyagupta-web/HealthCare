# Implementation Plan — Researcher Role

## Pre-work
- [x] Read `skills/access-control.md` and `skills/pii-masking.md`.
- [x] Confirmed no config or DB schema changes are required.
- [x] Confirmed `allowed_roles` is already a list on chunk metadata.

## Step 1 — DB / Config changes
None required. `researcher` is a query-time role string; no schema migration needed.

## Step 2 — Core logic

### 2a. RBAC policy (`ingestion/metadata/rbac_policy.py`)
- [x] Add `researcher` to `general` department allowed roles.
- [x] Add `researcher` to `cardiology` department allowed roles.
- [x] Verify `get_allowed_roles(department)` returns updated list.

### 2b. Role-based masking (`ingestion/pii/role_based_masking.py`)
- [x] Define `RESEARCHER_MASKED_ENTITIES` frozenset with: `PATIENT_NAME`, `MRN`, `DATE`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `SSN`, `PATIENT_DEMOGRAPHICS`.
- [x] Extend `apply_role_mask` dispatch to handle `"researcher"`.
- [x] Use `entity_types` field already on each chunk — do NOT re-detect with Presidio.
- [x] Replace masked entity tokens with `[REDACTED]` in chunk text.

## Step 3 — Security & Compliance
- [x] Masking uses `entity_types` from stored chunk metadata (ingest-time detection only).
- [x] `allowed_roles` written via `rbac_policy.py` — no inline hardcoding.
- [x] Call order: `filter_results_by_role` → `apply_role_mask` (enforced in search pipeline).
- [x] Audit log events unchanged — `QUERY_SUBMITTED` already covers researcher queries.

## Step 4 — Queue wiring
Not applicable — no new worker stage.

## Step 5 — Tests (`tests/unit/test_researcher_role.py`)
- [x] Unit: `apply_role_mask(chunk_with_patient_name, "researcher")` → no `[PATIENT_NAME]` in output.
- [x] Unit: `apply_role_mask(chunk_with_lab_value, "researcher")` → `[LAB_VALUE]` still present.
- [x] Unit: `apply_role_mask(chunk_with_mrn, "researcher")` → no `[MRN]` in output.
- [x] Integration: `filter_results_by_role(results, "researcher")` returns general/cardiology, not billing.
- [x] Integration: full pipeline — researcher gets masked chunks, no raw PII tokens.

## Step 6 — Eval
- Eval case `evals/case-03-researcher-role/` already exists with prompt and expected output.

## Step 7 — Documentation
- [x] `skills/access-control.md` role table updated with `researcher`.
- [x] `result-notes.md` written comparing implementation against `expected.md`.

## Rollback plan
Remove `"researcher"` from the `general` and `cardiology` lists in `rbac_policy.py` and delete the researcher branch in `apply_role_mask`. No data migration needed — chunks already stored without `researcher` in `allowed_roles` will simply remain inaccessible.
