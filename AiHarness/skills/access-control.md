# Skill: Access Control

## What this covers
Per-chunk RBAC: how roles are assigned at ingest, how they're enforced at query time.

## Roles
Defined in `ingestion/metadata/rbac_policy.py`. Department → allowed_roles mapping:

| Department | Allowed roles |
|---|---|
| `cardiology` | `doctor`, `nurse`, `cardiologist` |
| `billing` | `billing`, `admin` |
| `general` | `doctor`, `nurse`, `admin` |

New departments must be added to `rbac_policy.py` — never hardcode role lists inline.

## How roles attach to chunks

PiiWorker reads the document's department from metadata, looks up `rbac_policy.py`, and writes `allowed_roles` into every chunk's metadata before Chroma upsert:

```python
from ingestion.metadata.rbac_policy import get_allowed_roles

allowed_roles = get_allowed_roles(department=doc_metadata["department"])
chunk_metadata["allowed_roles"] = allowed_roles
```

## Filtering at query time

`security/access_control.py:filter_results_by_role(results, user_role)`:

```python
def filter_results_by_role(results: list[dict], user_role: str) -> list[dict]:
    return [
        r for r in results
        if user_role in r["metadata"].get("allowed_roles", [])
        or user_role == "admin"
    ]
```

`admin` has universal read access (metadata only — role masking still applies; see `skills/pii-masking.md`).

## Call order in search pipeline

```
reranked_results
  → filter_results_by_role(results, user_role)   ← RBAC
  → apply_role_mask(chunks, user_role)            ← PII masking
  → generate_answer(query, masked_chunks)         ← LLM
  → log_event("ANSWER_GENERATED", ...)            ← Audit
```

This order is non-negotiable. Swapping filter and mask breaks both systems.

## Adding a new role

1. Add the role string to `rbac_policy.py` under the relevant departments.
2. Add a masking rule for the role in `ingestion/pii/role_based_masking.py`.
3. Add an eval case under `evals/` that verifies the role sees/doesn't-see the right content.
4. Update `skills/pii-masking.md` role table.

## Bad examples

```python
# BAD: hardcoded role check inline
if user_role in ["doctor", "nurse", "cardiologist"]:
    return chunk  # bypasses rbac_policy.py, breaks when roles change

# BAD: calling filter after LLM
answer = generate_answer(query, all_chunks)
filtered = filter_results_by_role(all_chunks, role)  # LLM already saw forbidden chunks

# BAD: treating admin as superuser that skips masking
if user_role == "admin":
    return raw_chunks  # admin should still get role-masked output
```

## Failure modes seen
- Agent filters after calling the LLM — the LLM sees PHI it shouldn't, even if the final response is filtered.
- Agent gives `admin` unmasked clinical content — admin has metadata access only, clinical text still masked.
- Agent stores `allowed_roles` as a comma-delimited string instead of a list — `"doctor" in "doctor,nurse"` passes even for `"doc"`.

## Must NOT do
- Hardcode role lists anywhere outside `rbac_policy.py`.
- Filter results after LLM generation.
- Give any role access to un-masked clinical text unless that role is in `["doctor", "nurse", "cardiologist"]` and the document's department allows it.
- Store `allowed_roles` as a string — always a `list[str]`.
