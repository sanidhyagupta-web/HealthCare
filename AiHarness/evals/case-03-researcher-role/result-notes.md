# Eval Case 03 — Result Notes

## Date run
2026-05-25

## Outcome
- [x] Pass (≥ 80% criteria met)
- [ ] Partial pass (50–79%)
- [ ] Fail (< 50%)

**All criteria in expected.md met. 31/31 tests pass.**

---

## What the agent did

1. Read `Agents.md` and `skills/access-control.md` / `skills/pii-masking.md` before writing any code.
2. Created the feature folder `AiHarness/features/active/researcher-role/` with all three spec templates filled.
3. Created `ingestion/metadata/rbac_policy.py` — added `"researcher"` to `general` and `cardiology` department lists.
4. Created `ingestion/pii/role_based_masking.py` — defined `RESEARCHER_MASKED_ENTITIES` (7 forbidden entity types) and extended `apply_role_mask` dispatch.
5. Created `security/access_control.py` with `filter_results_by_role` exactly matching the pattern in `skills/access-control.md`.
6. Created `search/pipeline.py` — `secure_results()` wires `filter_results_by_role` → `apply_role_mask` in the correct order.
7. Created `tests/unit/test_researcher_role.py` with 31 tests covering unit masking, RBAC policy, and end-to-end `secure_results` scenarios.

---

## Criteria met

- [x] **Templates created and filled** — `01-product-spec.md`, `02-technical-spec.md`, `03-implementation-plan.md` all present in `features/active/researcher-role/`
- [x] **Correct skills referenced** — `skills/access-control.md` and `skills/pii-masking.md` read and followed; `apply_role_mask` pattern and call-order rules respected
- [x] **Implementation plan followed in order** — RBAC policy → masking rule → access_control → pipeline → tests (exactly the order specified in expected.md)
- [x] **Non-negotiables respected** (see detail below)
- [x] **Code style matches existing repo** — `from __future__ import annotations`, type hints, no inline comments explaining what the code does, docstrings match existing style

### Non-negotiables detail

| Rule | Status |
|---|---|
| `researcher` added only in `rbac_policy.py` — no hardcoded role strings elsewhere | ✅ |
| `apply_role_mask` dispatch is inside `role_based_masking.py` | ✅ |
| Masking called after `filter_results_by_role`, not before | ✅ (`search/pipeline.py` enforces this order) |
| Entity types read from chunk `entity_types` field — no Presidio re-detection at query time | ✅ |
| Researcher never receives `[PATIENT_NAME]` or `[MRN]` in unmasked form | ✅ (verified by `test_secure_results_researcher_no_patient_name_in_any_chunk` and `test_secure_results_researcher_no_mrn_in_any_chunk`) |
| Audit log unchanged — `QUERY_SUBMITTED` covers researcher queries | ✅ (no change required; noted in spec) |
| No hardcoded credentials or patient identifiers | ✅ |
| `allowed_roles` stored as `list[str]` not a string | ✅ |

---

## Files modified / created vs expected.md

| Expected | Actual | Match? |
|---|---|---|
| `ingestion/metadata/rbac_policy.py` — `researcher` in `general` and `cardiology` | Created with exact values | ✅ |
| `ingestion/pii/role_based_masking.py` — new masking rule for researcher | Created; uses `RESEARCHER_MASKED_ENTITIES` frozenset; replaces forbidden tokens with `[REDACTED]`; preserves `ICD10`, `LAB_VALUE`, `VITAL_SIGN`, `MEDICATION`, `DOSAGE_FREQ` | ✅ |
| `security/access_control.py` — `filter_results_by_role` | Created with identical logic to skill example | ✅ |
| Tests: unit `apply_role_mask(chunk_with_patient_name, "researcher")` → no `[PATIENT_NAME]` | `test_researcher_cannot_see_patient_name` — passes | ✅ |
| Tests: unit `apply_role_mask(chunk_with_lab_values, "researcher")` → `[LAB_VALUE]` intact | `test_researcher_can_see_lab_value` — passes | ✅ |
| Tests: integration `filter_results_by_role(results, "researcher")` returns general/cardiology, not billing | `test_researcher_gets_general_and_cardiology_but_not_billing` — passes | ✅ |

---

## Divergences from expected.md

**Minor / additive only — no violations:**

1. **`search/pipeline.py` added** — not required by expected.md but aligns with the call-order diagram in `skills/access-control.md`. It encapsulates `filter_results_by_role → apply_role_mask` in one `secure_results()` function so the pipeline ordering is impossible to violate by callers. This is strictly additive.

2. **Additional masking rules added** — `ADMIN_MASKED_ENTITIES` and `BILLING_MASKED_ENTITIES` were also defined in `role_based_masking.py`. The skill file's role table describes these roles, so their masking rules belong there. Expected.md did not explicitly list them, but they don't conflict and prevent future violations where admin/billing are accidentally left unmasked.

3. **31 tests vs 3 in expected.md** — the expected.md listed minimum tests. All 3 specified tests are present; 28 additional tests were added for edge cases (immutability, entity_types list update, `doctor`/`nurse` pass-through, etc.).

---

## Which skill needs sharpening?

None identified. Both `skills/access-control.md` and `skills/pii-masking.md` gave precise, unambiguous guidance that was followed without needing interpretation. The call-order diagram and the `apply_role_mask` / `filter_results_by_role` signatures in the skill files match the implementation exactly.

---

## Action taken

Feature is complete and all tests pass. No further action required.
