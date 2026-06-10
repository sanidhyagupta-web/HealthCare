# Eval Case 03 — Expected Output

## Templates
- [ ] `features/active/researcher-role/01-product-spec.md` — user is academic researcher, success criteria include: researcher sees ICD-10/lab values, researcher cannot see patient name/MRN, researcher gets access to general + cardiology departments
- [ ] `features/active/researcher-role/02-technical-spec.md` — architecture: "Security / RBAC"; touches `rbac_policy.py`, `role_based_masking.py`; skills: `access-control.md`, `pii-masking.md`
- [ ] `features/active/researcher-role/03-implementation-plan.md` — correct order: RBAC policy → masking rule → test

## Files modified

### `ingestion/metadata/rbac_policy.py`
```python
# researcher added to general and cardiology
"general": ["doctor", "nurse", "admin", "researcher"],
"cardiology": ["doctor", "nurse", "cardiologist", "researcher"],
```

### `ingestion/pii/role_based_masking.py`
New masking rule for `researcher`:
- Removes or replaces with `[REDACTED]`: any text segment tagged with `PATIENT_NAME`, `MRN`, `DATE`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `SSN`, `PATIENT_DEMOGRAPHICS`
- Leaves intact: `ICD10`, `LAB_VALUE`, `VITAL_SIGN`, `MEDICATION`, `DOSAGE_FREQ`, `DRUG_DOSE`

Implementation must use the entity_types field already on each chunk — not re-detect at query time.

## Conventions respected
- `researcher` added only to `rbac_policy.py` — no hardcoded role strings elsewhere
- Masking uses `apply_role_mask(chunk, role)` pattern — the role dispatch is inside `role_based_masking.py`
- Masking called after `filter_results_by_role`, not before
- `allowed_roles` for existing documents automatically includes `researcher` for general/cardiology departments after the policy change (no re-ingestion required)

## Non-negotiables respected
- Researcher role never receives a chunk containing `[PATIENT_NAME]` or `[MRN]` in unmasked form
- Role string `"researcher"` not hardcoded in `main.py` or `access_control.py` — only in `rbac_policy.py`
- Audit log still emits when researcher queries (same `QUERY_SUBMITTED` event)

## Tests expected
- Unit test: `apply_role_mask(chunk_with_patient_name, "researcher")` → output does not contain `[PATIENT_NAME]` token
- Unit test: `apply_role_mask(chunk_with_lab_values, "researcher")` → output still contains `HbA1c: 7.2%` or `[LAB_VALUE]`
- Integration test: `filter_results_by_role(results, "researcher")` returns chunks from general/cardiology but not billing department

## What failing looks like
- Agent adds researcher masking logic inside `access_control.py` instead of `role_based_masking.py`
- Agent hardcodes `["doctor", "nurse", "researcher"]` inline in `main.py`
- Agent applies masking before RBAC filter
- Agent re-detects PII at query time with Presidio instead of using `entity_types` field on chunks
- Agent gives researcher full clinical access "since we're already in a filtered context"
